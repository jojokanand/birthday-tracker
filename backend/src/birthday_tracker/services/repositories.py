"""Repository protocols.

Repositories are the storage boundary. Business logic depends on these
:class:`typing.Protocol` interfaces, not on any concrete adapter, which lets us
swap Firestore for an in-memory fake in unit tests without code changes.

**Tenant-isolation invariant.** Every owner-scoped method takes an
``owner_id`` and must not return data owned by a different user. A
``get`` for the wrong owner returns ``None`` rather than the document and
its 403 — the API layer translates that into a 404 to avoid existence
leaks.  The only methods that intentionally cross owners are
:meth:`CollectionRequestRepository.get_by_token_hash` (the form token is a
bearer credential; the route then operates within the request's
``owner_id``) and :meth:`UserRepository.list_all` (the daily digest
iterates every user).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from birthday_tracker.models import CollectionRequest, Contact, User


class ContactRepository(Protocol):
    """Persistence interface for :class:`~birthday_tracker.models.Contact`.

    Implementations live in :mod:`birthday_tracker.adapters`. All methods are
    asynchronous because the production adapter (Firestore) is async; the
    in-memory fake matches the signature so tests can swap them freely.
    """

    async def get(self, contact_id: UUID, owner_id: str) -> Contact | None:
        """Return the contact with the given ID if owned by ``owner_id``.

        Args:
            contact_id: Contact UUID to look up.
            owner_id: Firebase ``uid`` of the requesting user. The contact
                is returned only if its :attr:`Contact.owner_id` matches.

        Returns:
            The :class:`Contact` if it exists and is owned by ``owner_id``,
            else ``None``. A wrong-owner mismatch must look identical to a
            missing-document case so callers can't probe for existence
            across tenants.
        """
        ...  # pragma: no cover

    async def save(self, contact: Contact) -> None:
        """Insert or replace ``contact`` keyed by :attr:`Contact.id`.

        Implementations trust the :attr:`Contact.owner_id` attached to the
        model — the API layer is responsible for setting it from the
        authenticated identity.

        Args:
            contact: The contact to persist.
        """
        ...  # pragma: no cover

    async def delete(self, contact_id: UUID, owner_id: str) -> bool:
        """Delete the contact with the given ID if owned by ``owner_id``.

        Args:
            contact_id: Contact UUID to delete.
            owner_id: Firebase ``uid`` of the requesting user.

        Returns:
            ``True`` if a contact was deleted, ``False`` if no such contact
            existed for that owner. A wrong-owner mismatch returns ``False``
            without deleting anything.
        """
        ...  # pragma: no cover

    async def list_for_owner(self, owner_id: str) -> list[Contact]:
        """Return every contact owned by ``owner_id``.

        Args:
            owner_id: Firebase ``uid`` of the requesting user.

        Returns:
            All matching contacts in arbitrary order.
        """
        ...  # pragma: no cover


class CollectionRequestRepository(Protocol):
    """Persistence interface for :class:`~birthday_tracker.models.CollectionRequest`.

    Most lookups are scoped to the owner. The exception is
    :meth:`get_by_token_hash`, which is keyed by a bearer credential (the
    form token) and therefore intentionally crosses tenants — the form
    route then uses the returned request's ``owner_id`` to scope its work.
    """

    async def get(self, request_id: UUID, owner_id: str) -> CollectionRequest | None:
        """Fetch a request by its UUID if owned by ``owner_id``.

        Args:
            request_id: Request UUID.
            owner_id: Firebase ``uid`` of the requesting user.

        Returns:
            The :class:`CollectionRequest`, or ``None`` on mismatch / absence.
        """
        ...  # pragma: no cover

    async def get_by_token_hash(self, token_hash: str) -> CollectionRequest | None:
        """Fetch a request by the SHA-256 hex digest of its issued token.

        Intentionally not scoped by ``owner_id`` — the token is a bearer
        credential. Callers must read the resulting ``owner_id`` and use it
        to scope subsequent operations.

        Args:
            token_hash: Hex digest as produced by
                :func:`birthday_tracker.core.tokens.hash_token`.

        Returns:
            The :class:`CollectionRequest`, or ``None`` if no match.
        """
        ...  # pragma: no cover

    async def save(self, request: CollectionRequest) -> None:
        """Insert or replace ``request`` keyed by :attr:`CollectionRequest.id`.

        Implementations trust the :attr:`CollectionRequest.owner_id` on the
        model.

        Args:
            request: The request to persist.
        """
        ...  # pragma: no cover


class UserRepository(Protocol):
    """Persistence interface for :class:`~birthday_tracker.models.User`.

    Users are keyed by Firebase ``uid``. :meth:`list_all` intentionally
    crosses tenants; it's only called by the daily-digest scheduler.
    """

    async def get(self, user_id: str) -> User | None:
        """Fetch a user by ``uid``.

        Args:
            user_id: Firebase ``uid``.

        Returns:
            The :class:`User`, or ``None`` if no profile exists yet.
        """
        ...  # pragma: no cover

    async def save(self, user: User) -> None:
        """Insert or replace ``user`` keyed by :attr:`User.id`.

        Args:
            user: User profile to persist.
        """
        ...  # pragma: no cover

    async def list_all(self) -> list[User]:
        """Return every user profile.

        Used only by the daily digest endpoint to fan out per-owner work.

        Returns:
            All user profiles in arbitrary order.
        """
        ...  # pragma: no cover
