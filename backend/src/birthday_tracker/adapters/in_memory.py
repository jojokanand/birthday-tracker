"""In-memory implementations of the repository protocols.

Used by unit tests and by local development when a real Firestore is overkill.
The store is per-instance — construct a new one per test for isolation.
"""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from birthday_tracker.models import CollectionRequest, Contact


class InMemoryContactRepository:
    """A :class:`~birthday_tracker.services.ContactRepository` backed by a dict.

    Returned objects are deep-copied so mutations made by callers do not leak
    back into the store — this matches the behavior of a real database
    adapter, which always serializes through the wire.
    """

    def __init__(self) -> None:
        """Create an empty repository."""
        self._store: dict[UUID, Contact] = {}

    async def get(self, contact_id: UUID) -> Contact | None:
        """Return the stored contact for ``contact_id`` or ``None``.

        Args:
            contact_id: UUID to look up.

        Returns:
            A deep copy of the stored contact, or ``None`` if absent.
        """
        contact = self._store.get(contact_id)
        return deepcopy(contact) if contact is not None else None

    async def save(self, contact: Contact) -> None:
        """Insert or replace ``contact`` in the store.

        Args:
            contact: Contact to persist (deep-copied on the way in).
        """
        self._store[contact.id] = deepcopy(contact)

    async def delete(self, contact_id: UUID) -> bool:
        """Remove the contact with the given ID.

        Args:
            contact_id: UUID to delete.

        Returns:
            ``True`` if a contact was removed, ``False`` otherwise.
        """
        return self._store.pop(contact_id, None) is not None

    async def list_all(self) -> list[Contact]:
        """Return deep copies of every stored contact.

        Returns:
            All contacts in insertion order (Python 3.7+ dicts preserve it).
        """
        return [deepcopy(c) for c in self._store.values()]


class InMemoryCollectionRequestRepository:
    """A :class:`~birthday_tracker.services.CollectionRequestRepository` backed by a dict.

    Maintains a secondary index from ``token_hash`` to request ID so lookups
    by hash stay O(1).
    """

    def __init__(self) -> None:
        """Create an empty repository."""
        self._store: dict[UUID, CollectionRequest] = {}
        self._by_hash: dict[str, UUID] = {}

    async def get(self, request_id: UUID) -> CollectionRequest | None:
        """Fetch a request by its UUID.

        Args:
            request_id: UUID to look up.

        Returns:
            Deep copy of the stored request, or ``None``.
        """
        request = self._store.get(request_id)
        return deepcopy(request) if request is not None else None

    async def get_by_token_hash(self, token_hash: str) -> CollectionRequest | None:
        """Fetch a request by the hash of its issued form token.

        Args:
            token_hash: Hex SHA-256 digest of the raw token.

        Returns:
            Deep copy of the stored request, or ``None``.
        """
        request_id = self._by_hash.get(token_hash)
        return await self.get(request_id) if request_id is not None else None

    async def save(self, request: CollectionRequest) -> None:
        """Insert or replace ``request`` and update the token-hash index.

        Args:
            request: Request to persist.
        """
        self._store[request.id] = deepcopy(request)
        self._by_hash[request.token_hash] = request.id
