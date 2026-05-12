"""In-memory implementations of the repository protocols.

Used by unit tests and by local development when a real Firestore is overkill.
The store is per-instance — construct a new one per test for isolation.
"""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from birthday_tracker.models import CollectionRequest, Contact, User


class InMemoryContactRepository:
    """A :class:`~birthday_tracker.services.ContactRepository` backed by a dict.

    Returned objects are deep-copied so mutations made by callers do not leak
    back into the store — this matches the behavior of a real database
    adapter, which always serializes through the wire.

    Cross-tenant isolation is enforced by filtering on
    :attr:`Contact.owner_id` in every owner-scoped method.
    """

    def __init__(self) -> None:
        """Create an empty repository."""
        self._store: dict[UUID, Contact] = {}

    async def get(self, contact_id: UUID, owner_id: str) -> Contact | None:
        """Return the stored contact for ``contact_id`` if owned by ``owner_id``.

        Args:
            contact_id: UUID to look up.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            A deep copy of the stored contact, or ``None`` if the document
            is absent or owned by a different user.
        """
        contact = self._store.get(contact_id)
        if contact is None or contact.owner_id != owner_id:
            return None
        return deepcopy(contact)

    async def save(self, contact: Contact) -> None:
        """Insert or replace ``contact`` in the store.

        Args:
            contact: Contact to persist (deep-copied on the way in).
        """
        self._store[contact.id] = deepcopy(contact)

    async def delete(self, contact_id: UUID, owner_id: str) -> bool:
        """Remove the contact with the given ID if owned by ``owner_id``.

        Args:
            contact_id: UUID to delete.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            ``True`` if a contact was removed, ``False`` if it was absent
            or owned by a different user.
        """
        existing = self._store.get(contact_id)
        if existing is None or existing.owner_id != owner_id:
            return False
        del self._store[contact_id]
        return True

    async def list_for_owner(self, owner_id: str) -> list[Contact]:
        """Return deep copies of every stored contact owned by ``owner_id``.

        Args:
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            Matching contacts in insertion order (Python 3.7+ dicts
            preserve it).
        """
        return [deepcopy(c) for c in self._store.values() if c.owner_id == owner_id]


class InMemoryCollectionRequestRepository:
    """A :class:`~birthday_tracker.services.CollectionRequestRepository` backed by a dict.

    Maintains a secondary index from ``token_hash`` to request ID so lookups
    by hash stay O(1).
    """

    def __init__(self) -> None:
        """Create an empty repository."""
        self._store: dict[UUID, CollectionRequest] = {}
        self._by_hash: dict[str, UUID] = {}

    async def get(self, request_id: UUID, owner_id: str) -> CollectionRequest | None:
        """Fetch a request by its UUID if owned by ``owner_id``.

        Args:
            request_id: UUID to look up.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            Deep copy of the stored request, or ``None`` on absence /
            owner mismatch.
        """
        request = self._store.get(request_id)
        if request is None or request.owner_id != owner_id:
            return None
        return deepcopy(request)

    async def get_by_token_hash(self, token_hash: str) -> CollectionRequest | None:
        """Fetch a request by the hash of its issued form token.

        Not owner-scoped — the form token is a bearer credential. The
        caller is responsible for honoring the returned request's
        ``owner_id``.

        Args:
            token_hash: Hex SHA-256 digest of the raw token.

        Returns:
            Deep copy of the stored request, or ``None``.
        """
        request_id = self._by_hash.get(token_hash)
        if request_id is None:
            return None
        request = self._store.get(request_id)
        return deepcopy(request) if request is not None else None

    async def save(self, request: CollectionRequest) -> None:
        """Insert or replace ``request`` and update the token-hash index.

        Args:
            request: Request to persist.
        """
        self._store[request.id] = deepcopy(request)
        self._by_hash[request.token_hash] = request.id


class InMemoryUserRepository:
    """A :class:`~birthday_tracker.services.UserRepository` backed by a dict.

    The store is keyed by Firebase ``uid``. Returned objects are
    deep-copied to match real-database semantics.
    """

    def __init__(self) -> None:
        """Create an empty repository."""
        self._store: dict[str, User] = {}

    async def get(self, user_id: str) -> User | None:
        """Fetch a user profile by ``uid``.

        Args:
            user_id: Firebase ``uid``.

        Returns:
            Deep copy of the stored profile, or ``None`` if absent.
        """
        user = self._store.get(user_id)
        return deepcopy(user) if user is not None else None

    async def save(self, user: User) -> None:
        """Insert or replace ``user`` in the store.

        Args:
            user: User profile to persist (deep-copied on the way in).
        """
        self._store[user.id] = deepcopy(user)

    async def list_all(self) -> list[User]:
        """Return deep copies of every stored user profile.

        Returns:
            All profiles in insertion order.
        """
        return [deepcopy(u) for u in self._store.values()]
