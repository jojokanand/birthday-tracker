"""Public self-serve form router.

Two endpoints:

- ``GET /form/{token}`` — returns minimal metadata so the frontend can render
  a form bound to the right contact (greeting name, channel hint, etc.).
- ``POST /form/{token}`` — accepts the contact's submission, persists it, and
  marks the underlying :class:`CollectionRequest` fulfilled.

Both apply per-token rate limiting before doing any work.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from birthday_tracker.api.dependencies import (
    get_collection_request_service,
    get_form_rate_limiter,
)
from birthday_tracker.api.errors import APIError
from birthday_tracker.core.rate_limit import RateLimiter, RateLimitExceeded
from birthday_tracker.core.tokens import TokenExpired, TokenInvalid
from birthday_tracker.models import Address, Birthday
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
    FormSubmission,
    RequestNotPending,
)

router = APIRouter(prefix="/form", tags=["form"])


class FormMetadataResponse(BaseModel):
    """Returned by ``GET /form/{token}``.

    Attributes:
        greeting_name: First-name-style label safe to show in the form
            header. We never expose contact secrets via the public form.
        channel: Channel used to deliver the link.
        expires_at: ISO-8601 expiry timestamp.
    """

    greeting_name: str
    channel: str
    expires_at: str


class FormSubmissionBody(BaseModel):
    """Validated payload accepted by ``POST /form/{token}``."""

    full_name: str = Field(min_length=1, max_length=200)
    preferred_name: str | None = Field(default=None, max_length=100)
    address: Address
    birthday: Birthday


def _enforce_rate_limit(token: str, limiter: RateLimiter) -> None:
    """Hit ``limiter`` for ``token`` and convert overflow to a 429 problem+json.

    Args:
        token: Raw token from the URL path.
        limiter: Per-token :class:`RateLimiter`.

    Raises:
        APIError: 429 when the token has used up its allowance.
    """
    try:
        limiter.hit(token)
    except RateLimitExceeded as exc:
        raise APIError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            title="Too many requests",
            detail=str(exc),
        ) from exc


def _token_failure_to_api_error(exc: Exception) -> APIError:
    """Translate token / pending failures into the right HTTP status.

    Args:
        exc: The raised exception. Expected to be one of
            :class:`TokenInvalid`, :class:`TokenExpired`, or
            :class:`RequestNotPending`.

    Returns:
        An :class:`APIError` ready to raise with the matching status code.
        Tokens with bad signatures get 404 (we don't tell attackers whether
        a token would be valid otherwise); expired or already-fulfilled
        tokens get 410 Gone.
    """
    if isinstance(exc, TokenInvalid):
        return APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Form not found",
            detail="The link is invalid or has been mistyped.",
        )
    if isinstance(exc, TokenExpired | RequestNotPending):
        return APIError(
            status_code=status.HTTP_410_GONE,
            title="Form no longer available",
            detail=str(exc),
        )
    raise exc  # pragma: no cover - caller passed something we don't handle


@router.get(
    "/{token}",
    response_model=FormMetadataResponse,
    summary="Fetch metadata for a self-serve form",
    responses={
        404: {"description": "Token unknown or malformed"},
        410: {"description": "Token expired or request already fulfilled"},
        429: {"description": "Rate limit exceeded for this token"},
    },
)
async def get_form_metadata(
    token: str,
    service: Annotated[CollectionRequestService, Depends(get_collection_request_service)],
    limiter: Annotated[RateLimiter, Depends(get_form_rate_limiter)],
) -> FormMetadataResponse:
    """Return enough info for the frontend to render the form.

    Args:
        token: Raw signed token from the URL path.
        service: Injected :class:`CollectionRequestService`.
        limiter: Injected per-token rate limiter.

    Returns:
        :class:`FormMetadataResponse` describing the form for this token.

    Raises:
        APIError: 404 if the token is invalid, 410 if expired/used, 429 if
            rate-limited.
    """
    _enforce_rate_limit(token, limiter)
    try:
        request = await service.lookup(token)
    except (TokenInvalid, TokenExpired, RequestNotPending) as exc:
        raise _token_failure_to_api_error(exc) from exc

    # Token is the bearer credential — scope the contact lookup to the
    # request's recorded owner so we never expose another tenant's contact.
    contact = await service.contacts.get(request.contact_id, request.owner_id)
    greeting = (contact.preferred_name if contact else None) or "there"
    return FormMetadataResponse(
        greeting_name=greeting,
        channel=request.channel.value,
        expires_at=request.expires_at.isoformat(),
    )


@router.post(
    "/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Submit the self-serve form",
    responses={
        404: {"description": "Token unknown or contact missing"},
        410: {"description": "Token expired or request already fulfilled"},
        429: {"description": "Rate limit exceeded for this token"},
    },
)
async def submit_form(
    token: str,
    body: FormSubmissionBody,
    service: Annotated[CollectionRequestService, Depends(get_collection_request_service)],
    limiter: Annotated[RateLimiter, Depends(get_form_rate_limiter)],
) -> None:
    """Persist the contact's submission and mark the request fulfilled.

    Args:
        token: Raw signed token from the URL path.
        body: Validated submission payload.
        service: Injected :class:`CollectionRequestService`.
        limiter: Injected per-token rate limiter.

    Raises:
        APIError: 404 if token/contact missing, 410 if expired/used, 429
            if rate-limited.
    """
    _enforce_rate_limit(token, limiter)
    submission = FormSubmission(
        full_name=body.full_name,
        preferred_name=body.preferred_name,
        address=body.address,
        birthday=body.birthday,
    )
    try:
        await service.fulfill(token=token, submission=submission)
    except (TokenInvalid, TokenExpired, RequestNotPending) as exc:
        raise _token_failure_to_api_error(exc) from exc
    except ContactNotFound as exc:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Contact not found",
            detail=str(exc),
        ) from exc
