"""Owner-side router for issuing collection requests.

POST /collection-requests creates a pending request, mints a one-time signed
form token, and returns the URL the owner should send to the contact via SMS
or email (the actual delivery is the caller's job — usually the dashboard or
a CLI script).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from birthday_tracker.api.dependencies import (
    get_collection_request_service,
    require_user,
)
from birthday_tracker.api.errors import APIError
from birthday_tracker.core.auth import Identity
from birthday_tracker.models import Channel
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
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


class IssuedRequestResponse(BaseModel):
    """Response body returned by ``POST /collection-requests``."""

    request_id: UUID = Field(description="ID of the persisted CollectionRequest.")
    contact_id: UUID
    channel: Channel
    destination: str
    expires_at: str = Field(description="ISO-8601 expiry timestamp.")
    form_url: str = Field(description="Public URL to send to the contact.")


@router.post(
    "",
    response_model=IssuedRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new collection request",
)
async def issue_collection_request(
    body: IssueRequestBody,
    service: Annotated[CollectionRequestService, Depends(get_collection_request_service)],
    identity: Annotated[Identity, Depends(require_user)],
) -> IssuedRequestResponse:
    """Mint a token and persist a pending collection request for the caller.

    Args:
        body: Request payload with ``contact_id``, ``channel``, ``destination``.
        service: Injected :class:`CollectionRequestService`.
        identity: Authenticated caller — must own the referenced contact.

    Returns:
        :class:`IssuedRequestResponse` carrying the public form URL.

    Raises:
        APIError: 404 if no contact with ``contact_id`` is owned by the caller
            (this includes the case where the contact exists for a different
            user — we do not leak existence across tenants).
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

    return IssuedRequestResponse(
        request_id=issued.request.id,
        contact_id=issued.request.contact_id,
        channel=issued.request.channel,
        destination=issued.request.destination,
        expires_at=issued.request.expires_at.isoformat(),
        form_url=issued.url,
    )
