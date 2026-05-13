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

    def _filtered_sorted(self, owner_id: str, q: str | None) -> list[Contact]:
        """Owner-scoped, optionally q-filtered set sorted by ``(full_name_lower, id)``.

        Centralised so :meth:`list_page` and :meth:`count_for_owner` agree
        on the filter / order in every edge case.

        Args:
            owner_id: Firebase ``uid`` of the caller.
            q: Optional case-insensitive prefix search across the three
                lowercase mirror fields. Whitespace-only ``q`` is treated
                as no filter.

        Returns:
            Matching contacts (deep copies) in stable sort order.
        """
        normalised = (q or "").strip().lower()
        matches = [
            c for c in self._store.values() if c.owner_id == owner_id and _matches(c, normalised)
        ]
        matches.sort(key=lambda c: (c.full_name_lower, str(c.id)))
        return [deepcopy(c) for c in matches]

    async def list_page(
        self,
        owner_id: str,
        *,
        limit: int,
        cursor: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Contact], str | None]:
        """Return one page of contacts for ``owner_id`` ordered by name.

        Args:
            owner_id: Firebase ``uid`` of the caller.
            limit: Maximum items in the page.
            cursor: ``id`` of the last contact from the previous page,
                or ``None`` for the first page. A cursor that doesn't
                appear in the filtered set yields an empty page (matches
                the behaviour the router would observe if a doc was
                deleted between requests).
            q: Optional case-insensitive prefix search.

        Returns:
            ``(items, next_cursor)``.
        """
        sorted_items = self._filtered_sorted(owner_id, q)
        start = 0
        if cursor is not None:
            for index, item in enumerate(sorted_items):
                if str(item.id) == cursor:
                    start = index + 1
                    break
            else:
                return ([], None)
        page = sorted_items[start : start + limit]
        next_cursor = str(page[-1].id) if page and start + limit < len(sorted_items) else None
        return (page, next_cursor)

    async def count_for_owner(
        self,
        owner_id: str,
        *,
        q: str | None = None,
    ) -> int:
        """Return the number of contacts owned by ``owner_id`` (optionally filtered).

        Args:
            owner_id: Firebase ``uid`` of the caller.
            q: Optional case-insensitive prefix search across the three
                lowercase mirror fields.

        Returns:
            Total number of matching contacts.
        """
        return len(self._filtered_sorted(owner_id, q))


def _matches(contact: Contact, normalised_q: str) -> bool:
    """Return ``True`` when ``contact`` matches the normalised query string.

    A blank ``normalised_q`` matches everything. Otherwise the query is a
    case-insensitive prefix on any of ``full_name_lower``,
    ``preferred_name_lower``, or ``email_lower``.

    Args:
        contact: Contact to test.
        normalised_q: Already-trimmed, already-lowercased query string.
            An empty string skips the filter.

    Returns:
        ``True`` if the contact matches.
    """
    if not normalised_q:
        return True
    if contact.full_name_lower.startswith(normalised_q):
        return True
    if contact.preferred_name_lower and contact.preferred_name_lower.startswith(normalised_q):
        return True
    if contact.email_lower and contact.email_lower.startswith(normalised_q):
        return True
    return False


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
