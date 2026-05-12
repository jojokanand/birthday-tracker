"""Internal digest endpoints — used exclusively by Cloud Scheduler.

Both routes are protected by OIDC token validation.  Cloud Scheduler attaches
a short-lived OIDC token (``Authorization: Bearer <token>``) to each request.
The token audience is the Cloud Run service URL stored in
``Settings.digest_oidc_audience``.

When ``digest_oidc_audience`` is empty (dev / test), OIDC validation is
skipped so the endpoints remain usable without a real GCP project.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel

from birthday_tracker.api.dependencies import get_app_settings, get_contact_repository
from birthday_tracker.core.config import Settings
from birthday_tracker.core.logging import get_logger
from birthday_tracker.services.digest import DigestService, UpcomingBirthday
from birthday_tracker.services.repositories import ContactRepository

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
        days: The look-ahead window used.
        count: Number of upcoming birthdays found.
        items: The list of upcoming birthdays sorted by days_until.
    """

    days: int
    count: int
    items: list[UpcomingBirthdayResponse]


class DigestSendResponse(BaseModel):
    """Response body for ``POST /internal/digest/send``.

    Attributes:
        sent: Whether the email was delivered (``False`` means idempotent skip).
        date: The calendar date used as reference (ISO 8601).
        count: Number of upcoming birthdays included in the digest.
    """

    sent: bool
    date: str
    count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/upcoming",
    response_model=DigestUpcomingResponse,
    summary="List upcoming birthdays",
)
async def get_upcoming_birthdays(
    _auth: Annotated[None, Depends(require_scheduler_auth)],
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    days: Annotated[
        int,
        Query(ge=0, le=365, description="Look-ahead window in days (inclusive)."),
    ] = 14,
) -> DigestUpcomingResponse:
    """Return contacts whose birthday falls within the next *days* days.

    Intended for Cloud Scheduler health-check and for owner inspection.
    Protected by OIDC token validation when
    :attr:`~birthday_tracker.core.config.Settings.digest_oidc_audience` is set.

    Args:
        _auth: Resolved OIDC auth dependency (side-effect only).
        repo: Injected contact repository.
        days: Look-ahead window.

    Returns:
        Sorted list of upcoming birthdays with days-until counts.
    """
    service = DigestService(contacts=repo)
    upcoming = await service.get_upcoming(days=days)
    return DigestUpcomingResponse(
        days=days,
        count=len(upcoming),
        items=[UpcomingBirthdayResponse.from_domain(b) for b in upcoming],
    )


@router.post(
    "/send",
    response_model=DigestSendResponse,
    summary="Send the daily digest email",
)
async def send_digest(
    _auth: Annotated[None, Depends(require_scheduler_auth)],
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
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
    """Send the birthday digest email to the owner, or skip if already sent today.

    Cloud Scheduler should call this endpoint at 08:00 in the owner's
    timezone.  Duplicate calls on the same calendar date are idempotent:
    the second call returns ``sent: false`` without delivering another email.

    Args:
        _auth: Resolved OIDC auth dependency.
        repo: Injected contact repository.
        settings: Application settings (owner email, OIDC audience).
        days: Look-ahead window in days.
        today_override: Inject a fixed date for deterministic testing.

    Returns:
        :class:`DigestSendResponse` with ``sent`` flag and metadata.

    Raises:
        HTTPException: 503 if the owner email is not configured.
    """
    if not settings.digest_owner_email:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="digest_owner_email is not configured.",
        )

    # Build the Gmail notifier from settings.  Import lazily so the router can
    # be loaded in tests without real OAuth credentials.
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

    service = DigestService(contacts=repo)
    reference = today_override or dt.date.today()
    sent = await service.send_digest(
        notifier=notifier,
        owner_email=settings.digest_owner_email,
        days=days,
        today=reference,
    )
    upcoming = await service.get_upcoming(days=days, today=reference)
    return DigestSendResponse(
        sent=sent,
        date=reference.isoformat(),
        count=len(upcoming),
    )
