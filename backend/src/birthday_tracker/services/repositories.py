"""Repository protocols.

Repositories are the storage boundary. Business logic depends on these
:class:`typing.Protocol` interfaces, not on any concrete adapter, which lets us
swap Firestore for an in-memory fake in unit tests without code changes.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from birthday_tracker.models import CollectionRequest, Contact


class ContactRepository(Protocol):
    """Persistence interface for :class:`~birthday_tracker.models.Contact`.

    Implementations live in :mod:`birthday_tracker.adapters`. All methods are
    asynchronous because the production adapter (Firestore) is async; the
    in-memory fake matches the signature so tests can swap them freely.
    """

    async def get(self, contact_id: UUID) -> Contact | None:
        """Return the contact with the given ID or ``None`` if not found.

        Args:
            contact_id: Contact UUID to look up.

        Returns:
            The :class:`Contact` if it exists, else ``None``. Implementations
            must not raise on a missing contact — the caller decides whether
            absence is an error.
        """
        ...  # pragma: no cover

    async def save(self, contact: Contact) -> None:
        """Insert or replace ``contact`` keyed by :attr:`Contact.id`.

        Args:
            contact: The contact to persist. The repository assumes the
                caller has already called :meth:`Contact.touch` if relevant.
        """
        ...  # pragma: no cover

    async def delete(self, contact_id: UUID) -> bool:
        """Delete the contact with the given ID.

        Args:
            contact_id: Contact UUID to delete.

        Returns:
            ``True`` if a contact was deleted, ``False`` if no such contact
            existed. Lets the caller distinguish idempotent retries from
            unexpected misses.
        """
        ...  # pragma: no cover

    async def list_all(self) -> list[Contact]:
        """Return every stored contact.

        For a personal-use app this is fine. If the contact list grows past
        a few hundred we will introduce pagination as a follow-up issue.

        Returns:
            All contacts in arbitrary order.
        """
        ...  # pragma: no cover


class CollectionRequestRepository(Protocol):
    """Persistence interface for :class:`~birthday_tracker.models.CollectionRequest`.

    Lookups happen primarily by token-hash (the form endpoint receives a raw
    token, hashes it, and looks up the request) and by ID (for the owner UI).
    """

    async def get(self, request_id: UUID) -> CollectionRequest | None:
        """Fetch a request by its UUID.

        Args:
            request_id: Request UUID.

        Returns:
            The :class:`CollectionRequest`, or ``None`` if absent.
        """
        ...  # pragma: no cover

    async def get_by_token_hash(self, token_hash: str) -> CollectionRequest | None:
        """Fetch a request by the SHA-256 hex digest of its issued token.

        Args:
            token_hash: Hex digest as produced by
                :func:`birthday_tracker.core.tokens.hash_token`.

        Returns:
            The :class:`CollectionRequest`, or ``None`` if no match.
        """
        ...  # pragma: no cover

    async def save(self, request: CollectionRequest) -> None:
        """Insert or replace ``request`` keyed by :attr:`CollectionRequest.id`.

        Args:
            request: The request to persist.
        """
        ...  # pragma: no cover
