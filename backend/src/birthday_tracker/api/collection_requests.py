"""Owner-side router for issuing collection requests.

`POST /collection-requests` mints a one-time signed form token and persists a
pending request. The owner can either copy the returned URL out manually or
ask the backend to deliver it for them by setting ``send: true`` on the body
— in that mode the backend hands the link off to the matching channel
notifier (Twilio for SMS, Gmail API for email) and only reports success
once the provider acknowledges the send.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from birthday_tracker.api.dependencies import (
    get_collection_request_repository,
    get_collection_request_service,
    get_email_notifier,
    get_sms_notifier,
    require_user,
)
from birthday_tracker.api.errors import APIError
from birthday_tracker.core.auth import Identity
from birthday_tracker.models import Channel
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
)
from birthday_tracker.services.notifiers import (
    EmailNotifier,
    NotificationError,
    SmsNotifier,
)
from birthday_tracker.services.repositories import CollectionRequestRepository

router = APIRouter(prefix="/collection-requests", tags=["collection-requests"])


class IssueRequestBody(BaseModel):
    """Request body for ``POST /collection-requests``."""

    contact_id: UUID = Field(description="ID of the contact this request is for.")
    channel: Channel = Field(description="Delivery channel for the form link.")
    destination: str = Field(
        min_length=1,
        max_length=320,
        description="Phone number (E.164) or email address the link will be sent to.",
    )
    send: bool = Field(
        default=False,
        description=(
            "When true, the backend delivers the link via the matching "
            "notifier (Twilio for ``sms``, Gmail for ``email``) and only "
            "returns success once the provider acknowledges the send. When "
            "false (default), the backend just mints the link and returns "
            "the URL for the owner to deliver manually."
        ),
    )


class IssuedRequestResponse(BaseModel):
    """Response body returned by ``POST /collection-requests``."""

    request_id: UUID = Field(description="ID of the persisted CollectionRequest.")
    contact_id: UUID
    channel: Channel
    destination: str
    expires_at: str = Field(description="ISO-8601 expiry timestamp.")
    form_url: str = Field(description="Public URL to send to the contact.")
    sent: bool = Field(
        description=(
            "True when the backend successfully handed the link off to "
            "the configured notifier; false when ``send`` was not requested."
        ),
    )


_FORM_LINK_SUBJECT = "Quick favour — share your birthday and address"


def _email_body_html(form_url: str) -> str:
    """Render the HTML body sent when ``send=true`` and channel is email."""
    return (
        "<p>Hi!</p>"
        "<p>I'd like to keep your birthday and address handy so I don't "
        "miss them. Please use the link below to share your details — it "
        "expires in 7 days and can only be used once.</p>"
        f'<p><a href="{form_url}">{form_url}</a></p>'
        "<p>Thanks!</p>"
    )


def _sms_body(form_url: str) -> str:
    """Render the SMS body sent when ``send=true`` and channel is SMS."""
    return (
        "Hi! Please share your birthday and address using this one-time "
        f"link (expires in 7 days): {form_url}"
    )


@router.post(
    "",
    response_model=IssuedRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new collection request",
)
async def issue_collection_request(
    body: IssueRequestBody,
    service: Annotated[CollectionRequestService, Depends(get_collection_request_service)],
    requests: Annotated[
        CollectionRequestRepository,
        Depends(get_collection_request_repository),
    ],
    sms: Annotated[SmsNotifier | None, Depends(get_sms_notifier)],
    email: Annotated[EmailNotifier | None, Depends(get_email_notifier)],
    identity: Annotated[Identity, Depends(require_user)],
) -> IssuedRequestResponse:
    """Mint a signed form token, persist the request, and optionally deliver it.

    Args:
        body: ``contact_id``, ``channel``, ``destination``, plus the
            optional ``send`` flag.
        service: Injected :class:`CollectionRequestService`.
        requests: Injected :class:`CollectionRequestRepository` — used to
            roll back the persisted request if the notifier fails so we
            never leave a request the contact never received.
        sms: Configured :class:`SmsNotifier`, or ``None`` when the
            Twilio settings are unset on the running service.
        email: Configured :class:`EmailNotifier`, or ``None`` when the
            Gmail settings are unset on the running service.
        identity: Authenticated caller — must own the referenced contact.

    Returns:
        :class:`IssuedRequestResponse` with the form URL and a ``sent``
        flag indicating whether the notifier handoff succeeded.

    Raises:
        APIError: 404 if the contact isn't owned by the caller; 503
            when ``send=true`` but the matching notifier isn't
            configured on this deployment; 502 when the notifier was
            invoked but the upstream provider rejected the send (the
            persisted request is rolled back so a retry can re-mint a
            fresh token).
    """
    try:
        issued = await service.issue(
            contact_id=body.contact_id,
            channel=body.channel,
            destination=body.destination,
            owner_id=identity.user_id,
        )
    except ContactNotFound as exc:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Contact not found",
            detail=str(exc),
        ) from exc

    sent = False
    if body.send:
        try:
            await _deliver(
                channel=body.channel,
                destination=body.destination,
                form_url=issued.url,
                sms=sms,
                email=email,
            )
        except APIError:
            # Roll back the persisted request — leaving it in
            # ``pending`` would imply the contact had been notified.
            await requests.delete(issued.request.id, identity.user_id)
            raise
        except NotificationError as exc:
            await requests.delete(issued.request.id, identity.user_id)
            raise APIError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                title="Notification provider rejected the send",
                detail=(
                    "The link was minted but the email/SMS provider could "
                    "not deliver it. Please try again; if the failure "
                    "persists, generate the link manually and send it "
                    "yourself."
                ),
            ) from exc
        sent = True

    return IssuedRequestResponse(
        request_id=issued.request.id,
        contact_id=issued.request.contact_id,
        channel=issued.request.channel,
        destination=issued.request.destination,
        expires_at=issued.request.expires_at.isoformat(),
        form_url=issued.url,
        sent=sent,
    )


async def _deliver(
    *,
    channel: Channel,
    destination: str,
    form_url: str,
    sms: SmsNotifier | None,
    email: EmailNotifier | None,
) -> None:
    """Hand the form link to the matching channel notifier.

    Raises:
        APIError: 503 when the notifier for the chosen channel is not
            configured on this deployment.
        NotificationError: Re-raised from the notifier's ``send`` so the
            route can roll back and translate to a 502.
    """
    if channel is Channel.email:
        if email is None:
            raise APIError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Email delivery is not configured",
                detail=(
                    "The backend is missing the Gmail credentials needed "
                    "to send this link. Generate the link instead and "
                    "deliver it manually, or ask an admin to configure "
                    "Gmail."
                ),
            )
        await email.send(
            to=destination,
            subject=_FORM_LINK_SUBJECT,
            html=_email_body_html(form_url),
        )
        return
    if channel is Channel.sms:
        if sms is None:
            raise APIError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="SMS delivery is not configured",
                detail=(
                    "The backend is missing the Twilio credentials needed "
                    "to send this link. Generate the link instead and "
                    "deliver it manually, or ask an admin to configure "
                    "Twilio."
                ),
            )
        await sms.send(to=destination, body=_sms_body(form_url))
        return
    # No other Channel values exist; this guard keeps mypy honest if
    # one is added without updating this dispatch.
    raise APIError(  # pragma: no cover - defensive
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Unsupported channel",
        detail=f"Channel {channel!r} is not handled.",
    )
