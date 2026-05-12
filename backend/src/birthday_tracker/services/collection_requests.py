"""Business logic for issuing and fulfilling collection requests.

The service owns the orchestration that the HTTP routes don't:

- minting a token that expires and is single-use,
- persisting a request whose ``token_hash`` lets the form endpoint find it
  without ever storing the raw token,
- on submission, updating the contact and marking the request fulfilled in
  a single transactional step (well — two writes; if we ever care about
  atomicity we'll do this in a Firestore transaction).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from birthday_tracker.core.tokens import (
    TokenError,
    TokenExpired,
    TokenInvalid,
    hash_token,
    sign_token,
    verify_token,
)
from birthday_tracker.models import (
    Address,
    Birthday,
    Channel,
    CollectionRequest,
    Contact,
)
from birthday_tracker.services.repositories import (
    CollectionRequestRepository,
    ContactRepository,
)


class CollectionRequestServiceError(Exception):
    """Base class for service-level errors."""


class ContactNotFound(CollectionRequestServiceError):
    """Raised when the contact a new request points at does not exist."""


class RequestNotPending(CollectionRequestServiceError):
    """Raised when fulfilling a request that has already been used or expired."""


@dataclass(frozen=True)
class IssuedRequest:
    """Returned by :meth:`CollectionRequestService.issue`.

    Attributes:
        request: The persisted :class:`CollectionRequest`.
        token: The raw signed token. Surfaced exactly once — call sites
            must embed it in the outbound SMS/email link, then drop it.
        url: Convenience full link composed of ``public_base_url`` +
            ``/form/<token>``.
    """

    request: CollectionRequest
    token: str
    url: str


@dataclass(frozen=True)
class FormSubmission:
    """Caller payload for :meth:`CollectionRequestService.fulfill`.

    Attributes:
        full_name: Updated full legal/common name.
        preferred_name: Optional preferred name.
        address: Postal address.
        birthday: Birthday (month/day required, year optional).
    """

    full_name: str
    preferred_name: str | None
    address: Address
    birthday: Birthday


class CollectionRequestService:
    """Orchestrates the request → token → submission flow.

    Attributes:
        contacts: Contact repository.
        requests: Collection-request repository.
        token_secret: HMAC key used for signing and verifying tokens.
        token_ttl_seconds: Lifetime in seconds of newly-issued tokens.
        public_base_url: Public base URL used to build form links.
    """

    def __init__(
        self,
        *,
        contacts: ContactRepository,
        requests: CollectionRequestRepository,
        token_secret: str,
        token_ttl_seconds: int,
        public_base_url: str,
    ) -> None:
        """Build the service.

        Args:
            contacts: :class:`ContactRepository` injection point.
            requests: :class:`CollectionRequestRepository` injection point.
            token_secret: HMAC key. Must be non-empty.
            token_ttl_seconds: Token lifetime; must be positive.
            public_base_url: Base URL for outbound links (without trailing slash).

        Raises:
            ValueError: If ``token_secret`` is empty or ``token_ttl_seconds``
                is non-positive.
        """
        if not token_secret:
            raise ValueError("token_secret must be non-empty")
        if token_ttl_seconds <= 0:
            raise ValueError("token_ttl_seconds must be positive")
        self.contacts = contacts
        self.requests = requests
        self.token_secret = token_secret
        self.token_ttl_seconds = token_ttl_seconds
        self.public_base_url = public_base_url.rstrip("/")

    async def issue(self, *, contact_id: UUID, channel: Channel, destination: str) -> IssuedRequest:
        """Mint a fresh token and persist a pending request.

        Args:
            contact_id: ID of the existing contact this request is for.
            channel: Whether the link will be delivered by SMS or email.
            destination: The phone or email address the link is sent to.

        Returns:
            An :class:`IssuedRequest` with the persisted record + raw token + URL.

        Raises:
            ContactNotFound: If no contact with ``contact_id`` exists.
        """
        contact = await self.contacts.get(contact_id)
        if contact is None:
            raise ContactNotFound(str(contact_id))

        request = CollectionRequest(
            contact_id=contact.id,
            channel=channel,
            destination=destination,
            token_hash="0" * 64,  # placeholder — replaced below once we have the token
            expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(seconds=self.token_ttl_seconds),
        )
        token = sign_token(
            request_id=request.id,
            ttl_seconds=self.token_ttl_seconds,
            secret=self.token_secret,
        )
        # Replace the placeholder hash now that we know the real token.
        request = request.model_copy(update={"token_hash": hash_token(token)})
        await self.requests.save(request)

        return IssuedRequest(
            request=request,
            token=token,
            url=f"{self.public_base_url}/form/{token}",
        )

    async def lookup(self, token: str) -> CollectionRequest:
        """Verify ``token`` and return the matching :class:`CollectionRequest`.

        Args:
            token: Raw form token from the URL.

        Returns:
            The pending :class:`CollectionRequest`.

        Raises:
            TokenInvalid: Token signature is wrong, malformed, or unknown.
            TokenExpired: Token signature is valid but past its ``exp``.
            RequestNotPending: Token is valid but the request has already
                been fulfilled (single-use enforcement).
        """
        payload = verify_token(token, self.token_secret)
        request = await self.requests.get_by_token_hash(hash_token(token))
        if request is None or request.id != payload.request_id:
            raise TokenInvalid("unknown token")
        if not request.is_pending:
            raise RequestNotPending("request has already been fulfilled or expired")
        return request

    async def fulfill(self, *, token: str, submission: FormSubmission) -> Contact:
        """Apply ``submission`` to the contact and mark the request fulfilled.

        Args:
            token: Raw form token from the URL.
            submission: Validated form payload.

        Returns:
            The updated :class:`Contact`.

        Raises:
            TokenInvalid, TokenExpired, RequestNotPending: As :meth:`lookup`.
            ContactNotFound: If the underlying contact has been deleted
                between issue and fulfill.
        """
        request = await self.lookup(token)
        contact = await self.contacts.get(request.contact_id)
        if contact is None:
            raise ContactNotFound(str(request.contact_id))

        updated = contact.model_copy(
            update={
                "full_name": submission.full_name,
                "preferred_name": submission.preferred_name,
                "address": submission.address,
                "birthday": submission.birthday,
            },
        )
        updated.touch()
        await self.contacts.save(updated)

        fulfilled = request.model_copy(update={"fulfilled_at": dt.datetime.now(dt.UTC)})
        await self.requests.save(fulfilled)
        return updated


# Re-export the token errors so callers don't need to dip into core.tokens.
__all__ = [
    "CollectionRequestService",
    "CollectionRequestServiceError",
    "ContactNotFound",
    "FormSubmission",
    "IssuedRequest",
    "RequestNotPending",
    "TokenError",
    "TokenExpired",
    "TokenInvalid",
]
