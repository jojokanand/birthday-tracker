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
    get_app_settings,
    get_collection_request_repository,
    get_collection_request_service,
    get_contact_repository,
    get_email_notifier,
    get_sms_notifier,
    require_user,
)
from birthday_tracker.api.errors import APIError
from birthday_tracker.core.auth import Identity
from birthday_tracker.core.config import Settings
from birthday_tracker.models import Channel, Contact
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
)
from birthday_tracker.services.notifiers import (
    EmailNotifier,
    NotificationError,
    SmsNotifier,
)
from birthday_tracker.services.repositories import (
    CollectionRequestRepository,
    ContactRepository,
)

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


_PRODUCT_NAME = "Birthday Genie"
_OWNER_FALLBACK = "Someone"
_CONTACT_FALLBACK = "there"


def _first_token(value: str | None) -> str | None:
    """Return the first whitespace-separated token of ``value``, trimmed.

    Returns ``None`` when ``value`` is empty / whitespace-only so the
    caller can chain through preferred-name → full-name → static
    fallback without conditional ladders.
    """
    if not value:
        return None
    parts = value.strip().split()
    return parts[0] if parts else None


def _contact_first_name(contact: Contact) -> str:
    """Best guess at how to address the contact in greetings.

    Prefers :attr:`Contact.preferred_name` when set, then the first
    token of :attr:`Contact.full_name`, and finally ``"there"`` so the
    greeting never reads ``Hi !``.
    """
    return (
        _first_token(contact.preferred_name) or _first_token(contact.full_name) or _CONTACT_FALLBACK
    )


def _owner_first_name(identity: Identity) -> str:
    """Best guess at the owner's first name for the email subject + body.

    Pulled from the Firebase ``name`` claim via
    :attr:`Identity.display_name`. Falls back to ``"Someone"`` when the
    claim is absent (legacy accounts; the dev identity supplies a
    placeholder so local development still reads naturally).
    """
    return _first_token(identity.display_name) or _OWNER_FALLBACK


def _email_subject(owner_first_name: str) -> str:
    """Subject line: identifies the sender + the product."""
    return f"{owner_first_name} is using {_PRODUCT_NAME} — share your birthday"


def _email_body_html(
    *,
    form_url: str,
    contact_first_name: str,
    owner_first_name: str,
    sign_up_url: str,
) -> str:
    """HTML body sent when ``send=true`` and channel is email."""
    return (
        f"<p>Hi {contact_first_name}!</p>"
        f"<p>{owner_first_name} is using <strong>{_PRODUCT_NAME}</strong> "
        "to keep birthdays and addresses for the people they care about. "
        "They've asked you to share yours — please use this "
        f'<a href="{form_url}">link</a> to fill in your details. It '
        "expires in 7 days and can only be used once.</p>"
        '<p style="color:#666;font-size:0.9em">'
        "If the link doesn't open, copy and paste this URL into your "
        f"browser:<br/>{form_url}</p>"
        '<hr style="border:0;border-top:1px solid #eee;margin:24px 0"/>'
        "<p>"
        f"Interested in checking out {_PRODUCT_NAME}? "
        f'<a href="{sign_up_url}">Sign up here</a>.</p>'
    )


def _email_body_text(
    *,
    form_url: str,
    contact_first_name: str,
    owner_first_name: str,
    sign_up_url: str,
) -> str:
    """Plain-text alternative shipped alongside the HTML body."""
    return (
        f"Hi {contact_first_name}!\n\n"
        f"{owner_first_name} is using {_PRODUCT_NAME} to keep birthdays "
        "and addresses for the people they care about. They've asked "
        "you to share yours — please use the link below to fill in "
        "your details. It expires in 7 days and can only be used once.\n\n"
        f"{form_url}\n\n"
        "—\n\n"
        f"Interested in checking out {_PRODUCT_NAME}? Sign up here:\n"
        f"{sign_up_url}\n"
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
    contacts: Annotated[ContactRepository, Depends(get_contact_repository)],
    sms: Annotated[SmsNotifier | None, Depends(get_sms_notifier)],
    email: Annotated[EmailNotifier | None, Depends(get_email_notifier)],
    settings: Annotated[Settings, Depends(get_app_settings)],
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
        contacts: Injected :class:`ContactRepository` — used by the
            ``send=true`` path to look up the contact's first name for
            the email greeting.
        sms: Configured :class:`SmsNotifier`, or ``None`` when the
            Twilio settings are unset on the running service.
        email: Configured :class:`EmailNotifier`, or ``None`` when the
            Gmail settings are unset on the running service.
        settings: Injected :class:`Settings` — used to build the
            "Sign up here" URL out of ``public_base_url``.
        identity: Authenticated caller — must own the referenced contact.
            ``identity.display_name`` is the source for the owner's
            first name in the email subject + body.

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
        # The contact existence was already verified by service.issue,
        # so the fetch here is just to read it (re-uses the same repo).
        # The token bearer credential bound to the request authorises
        # the per-owner scope.
        contact = await contacts.get(body.contact_id, identity.user_id)
        if contact is None:  # pragma: no cover - service.issue would have failed
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Contact not found",
                detail=f"No contact with ID {body.contact_id}",
            )
        try:
            await _deliver(
                channel=body.channel,
                destination=body.destination,
                form_url=issued.url,
                contact=contact,
                identity=identity,
                sign_up_url=settings.public_base_url,
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
    contact: Contact,
    identity: Identity,
    sign_up_url: str,
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
        contact_first = _contact_first_name(contact)
        owner_first = _owner_first_name(identity)
        await email.send(
            to=destination,
            subject=_email_subject(owner_first),
            html=_email_body_html(
                form_url=form_url,
                contact_first_name=contact_first,
                owner_first_name=owner_first,
                sign_up_url=sign_up_url,
            ),
            text=_email_body_text(
                form_url=form_url,
                contact_first_name=contact_first,
                owner_first_name=owner_first,
                sign_up_url=sign_up_url,
            ),
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
