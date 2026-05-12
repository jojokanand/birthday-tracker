"""Internal digest endpoints — used exclusively by Cloud Scheduler.

Both routes are protected by OIDC token validation. Cloud Scheduler attaches
a short-lived OIDC token (``Authorization: Bearer <token>``) to each request.
The token audience is the Cloud Run service URL stored in
``Settings.digest_oidc_audience``.

When ``digest_oidc_audience`` is empty (dev / test), OIDC validation is
skipped so the endpoints remain usable without a real GCP project.

With multi-tenant support, ``POST /send`` fans out across all known users
and delivers each their own digest. A per-user failure (e.g. Gmail error)
is logged and skipped without aborting the others.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel

from birthday_tracker.api.dependencies import (
    get_app_settings,
    get_contact_repository,
    get_user_repository,
)
from birthday_tracker.core.config import Settings
from birthday_tracker.core.logging import get_logger
from birthday_tracker.services.digest import DigestService, UpcomingBirthday
from birthday_tracker.services.repositories import ContactRepository, UserRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/internal/digest", tags=["digest"])


# ---------------------------------------------------------------------------
# OIDC authentication
# ---------------------------------------------------------------------------


def _verify_oidc(token: str, audience: str) -> None:
    """Validate a Google OIDC token.

    Args:
        token: Raw Bearer token string.
        audience: Expected ``aud`` claim (Cloud Run service URL).

    Raises:
        HTTPException: 401 if the token is absent, invalid, or has the wrong
            audience.
    """
    from google.auth.transport import requests as google_requests  # noqa: PLC0415
    from google.oauth2 import id_token  # noqa: PLC0415

    try:
        id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token,
            google_requests.Request(),
            audience=audience,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("oidc_validation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC token.",
        ) from exc


def require_scheduler_auth(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str, Header()] = "",
) -> None:
    """FastAPI dependency that validates the Cloud Scheduler OIDC token.

    When :attr:`~birthday_tracker.core.config.Settings.digest_oidc_audience`
    is empty (local dev / CI), validation is skipped entirely.

    Args:
        settings: Application settings.
        authorization: ``Authorization`` header value, injected by FastAPI.

    Raises:
        HTTPException: 401 when OIDC validation is configured and fails.
    """
    audience = settings.digest_oidc_audience
    if not audience:
        return  # dev / test: skip auth

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
        )
    token = authorization[len("bearer ") :]
    _verify_oidc(token, audience)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UpcomingBirthdayResponse(BaseModel):
    """Wire representation of :class:`~birthday_tracker.services.digest.UpcomingBirthday`.

    Attributes:
        contact_id: UUID string of the contact.
        full_name: Contact's full legal name.
        preferred_name: Nickname, if set.
        days_until: Days until the next birthday occurrence (0 = today).
    """

    contact_id: str
    full_name: str
    preferred_name: str | None
    days_until: int

    @classmethod
    def from_domain(cls, b: UpcomingBirthday) -> UpcomingBirthdayResponse:
        """Convert a domain :class:`~birthday_tracker.services.digest.UpcomingBirthday`.

        Args:
            b: Domain object to convert.

        Returns:
            Wire-safe response model.
        """
        return cls(
            contact_id=b.contact_id,
            full_name=b.full_name,
            preferred_name=b.preferred_name,
            days_until=b.days_until,
        )


class DigestUpcomingResponse(BaseModel):
    """Response body for ``GET /internal/digest/upcoming``.

    Attributes:
        owner_id: Owner whose upcoming birthdays are listed.
        days: The look-ahead window used.
        count: Number of upcoming birthdays found.
        items: The list of upcoming birthdays sorted by days_until.
    """

    owner_id: str
    days: int
    count: int
    items: list[UpcomingBirthdayResponse]


class DigestUserResult(BaseModel):
    """Per-user outcome inside :class:`DigestSendResponse`.

    Attributes:
        owner_id: Firebase ``uid`` of the user this entry describes.
        owner_email: Address the digest was (or would be) sent to.
        sent: Whether an email was actually delivered.
        count: Number of upcoming birthdays in the digest.
        error: Failure message if delivery raised. ``None`` on success.
    """

    owner_id: str
    owner_email: str
    sent: bool
    count: int
    error: str | None = None


class DigestSendResponse(BaseModel):
    """Response body for ``POST /internal/digest/send``.

    Attributes:
        date: The calendar date used as reference (ISO 8601).
        users: Per-user outcome — one entry per known profile.
        delivered: Total emails actually sent across all users.
        skipped: Users who would have received a digest but the
            per-process idempotency guard suppressed it.
        failed: Users whose delivery raised an exception (continued).
    """

    date: str
    users: list[DigestUserResult]
    delivered: int
    skipped: int
    failed: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/upcoming",
    response_model=DigestUpcomingResponse,
    summary="List one owner's upcoming birthdays (admin debug)",
)
async def get_upcoming_birthdays(
    _auth: Annotated[None, Depends(require_scheduler_auth)],
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    owner_id: Annotated[
        str,
        Query(description="Firebase uid of the user to inspect."),
    ],
    days: Annotated[
        int,
        Query(ge=0, le=365, description="Look-ahead window in days (inclusive)."),
    ] = 14,
) -> DigestUpcomingResponse:
    """Return the upcoming birthdays for a specific owner.

    Intended for debugging and Cloud Scheduler health-check probes.
    Protected by OIDC validation when configured; otherwise wide-open in
    development.

    Args:
        _auth: Resolved OIDC auth dependency (side-effect only).
        repo: Injected contact repository.
        owner_id: Firebase ``uid`` whose contacts to load.
        days: Look-ahead window.

    Returns:
        Sorted list of upcoming birthdays for the requested owner.
    """
    service = DigestService(contacts=repo)
    upcoming = await service.get_upcoming(owner_id=owner_id, days=days)
    return DigestUpcomingResponse(
        owner_id=owner_id,
        days=days,
        count=len(upcoming),
        items=[UpcomingBirthdayResponse.from_domain(b) for b in upcoming],
    )


@router.post(
    "/send",
    response_model=DigestSendResponse,
    summary="Send the daily digest email to every user",
)
async def send_digest(
    _auth: Annotated[None, Depends(require_scheduler_auth)],
    contacts: Annotated[ContactRepository, Depends(get_contact_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    days: Annotated[
        int,
        Query(ge=0, le=365, description="Look-ahead window in days (inclusive)."),
    ] = 14,
    today_override: Annotated[
        dt.date | None,
        Query(
            alias="today",
            description="Override today's date (ISO 8601). Test use only.",
        ),
    ] = None,
) -> DigestSendResponse:
    """Iterate every user profile and send each their own daily digest.

    Cloud Scheduler should call this endpoint once per morning. Each user
    receives a digest of their own contacts at their own preferred email.
    A failure for one user (e.g. Gmail API error) is logged and skipped
    so the rest of the fan-out still completes.

    Args:
        _auth: Resolved OIDC auth dependency.
        contacts: Contact repository (used per-owner).
        users: User repository — iterated to find every owner.
        settings: Process settings (Gmail OAuth paths, from-address).
        days: Look-ahead window in days.
        today_override: Inject a fixed date for deterministic testing.

    Returns:
        :class:`DigestSendResponse` summarising the fan-out outcome.
    """
    # Build the Gmail notifier once and reuse across all users.  Import
    # lazily so the router can be loaded in tests without real OAuth
    # credentials.
    from birthday_tracker.adapters import (  # noqa: PLC0415
        GmailNotifier,
        build_gmail_service,
        load_gmail_credentials,
    )

    creds = load_gmail_credentials(
        client_secrets_path=settings.gmail_oauth_client_secrets_path,
        token_path=settings.gmail_oauth_token_path,
    )
    gmail_service = build_gmail_service(creds)
    notifier = GmailNotifier(service=gmail_service, from_address=settings.gmail_from_address)

    reference = today_override or dt.date.today()
    service = DigestService(contacts=contacts)

    results: list[DigestUserResult] = []
    delivered = 0
    skipped = 0
    failed = 0

    for user in await users.list_all():
        owner_email = user.effective_digest_email
        try:
            was_sent = await service.send_digest(
                notifier=notifier,
                owner_id=user.id,
                owner_email=owner_email,
                days=days,
                today=reference,
            )
        except Exception as exc:  # noqa: BLE001 — record and continue
            logger.warning("digest_send_failed", owner_id=user.id, error=str(exc))
            failed += 1
            results.append(
                DigestUserResult(
                    owner_id=user.id,
                    owner_email=owner_email,
                    sent=False,
                    count=0,
                    error=str(exc),
                )
            )
            continue

        upcoming = await service.get_upcoming(owner_id=user.id, days=days, today=reference)
        if was_sent:
            delivered += 1
        else:
            skipped += 1
        results.append(
            DigestUserResult(
                owner_id=user.id,
                owner_email=owner_email,
                sent=was_sent,
                count=len(upcoming),
            )
        )

    return DigestSendResponse(
        date=reference.isoformat(),
        users=results,
        delivered=delivered,
        skipped=skipped,
        failed=failed,
    )
