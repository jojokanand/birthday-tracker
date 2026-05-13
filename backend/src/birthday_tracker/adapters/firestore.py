"""Firestore-backed implementation of the repository protocols.

Contacts and collection requests live in top-level collections keyed by
their UUID with an ``owner_id`` field used to filter per-tenant queries
(see [infra/README.md](../../../../infra/README.md) for the required
composite indexes). User profiles live in a ``users`` collection keyed by
Firebase ``uid``.

We round-trip Pydantic models via ``model_dump(mode="json")`` so all
values (UUIDs, datetimes, enums, nested Address/Birthday models) become
Firestore-compatible primitives without bespoke serialization logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from birthday_tracker.core.logging import get_logger
from birthday_tracker.models import CollectionRequest, Contact, User

if TYPE_CHECKING:  # pragma: no cover - typing only
    from google.cloud.firestore import AsyncClient

logger = get_logger(__name__)

CONTACTS_COLLECTION = "contacts"
COLLECTION_REQUESTS_COLLECTION = "collection_requests"
USERS_COLLECTION = "users"


def build_async_client(project_id: str) -> AsyncClient:
    """Construct a Firestore :class:`AsyncClient`.

    Importing :mod:`google.cloud.firestore` lazily here keeps the adapter
    module importable in environments without GCP libraries (e.g. when other
    tests only need the protocol or the in-memory fake).

    Args:
        project_id: GCP project ID. When the ``FIRESTORE_EMULATOR_HOST``
            environment variable is set, the SDK ignores credentials and
            talks to the emulator instead.

    Returns:
        A configured async Firestore client.
    """
    from google.cloud import firestore  # noqa: PLC0415

    return firestore.AsyncClient(project=project_id or "demo-project")


class FirestoreContactRepository:
    """A :class:`~birthday_tracker.services.ContactRepository` backed by Firestore.

    Tenant isolation is enforced by filtering every owner-scoped read on
    the ``owner_id`` field. Wrong-owner lookups return ``None`` rather
    than the document so callers cannot probe for cross-tenant existence.

    Attributes:
        client: The :class:`google.cloud.firestore.AsyncClient` used for I/O.
            Injected so tests can supply a client pointed at the emulator.
        collection_name: Name of the Firestore collection. Overridable so
            integration tests can use a unique per-test collection and clean
            up trivially.
    """

    def __init__(self, client: AsyncClient, collection_name: str = CONTACTS_COLLECTION) -> None:
        """Build the repository.

        Args:
            client: Pre-built Firestore async client.
            collection_name: Collection name. Defaults to ``"contacts"``.
        """
        self.client = client
        self.collection_name = collection_name

    def _doc_ref(self, contact_id: UUID) -> Any:
        """Return the Firestore document reference for ``contact_id``.

        Args:
            contact_id: The contact UUID.

        Returns:
            A :class:`AsyncDocumentReference` pointing at the document. The
            return type is ``Any`` because the SDK's type stubs are
            incomplete — runtime behavior is well-defined.
        """
        return self.client.collection(self.collection_name).document(str(contact_id))

    async def get(self, contact_id: UUID, owner_id: str) -> Contact | None:
        """Fetch a contact by ID if owned by ``owner_id``.

        Args:
            contact_id: UUID to look up.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            The :class:`Contact`, or ``None`` if no document exists or the
            stored owner does not match.
        """
        snapshot = await self._doc_ref(contact_id).get()
        if not snapshot.exists:
            return None
        contact = Contact.model_validate(snapshot.to_dict())
        if contact.owner_id != owner_id:
            return None
        return contact

    async def save(self, contact: Contact) -> None:
        """Upsert ``contact`` into the collection.

        Args:
            contact: Contact to persist. The caller has already set
                :attr:`Contact.owner_id` from the authenticated identity.
        """
        payload = contact.model_dump(mode="json")
        await self._doc_ref(contact.id).set(payload)
        logger.info("contact_saved", contact_id=str(contact.id), owner_id=contact.owner_id)

    async def delete(self, contact_id: UUID, owner_id: str) -> bool:
        """Delete a contact if owned by ``owner_id``.

        Firestore's ``delete()`` is idempotent — it succeeds even when the
        document does not exist. We do an explicit existence + owner check
        first so the caller can distinguish a deletion from a no-op retry
        and so we never delete another user's data.

        Args:
            contact_id: UUID to delete.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            ``True`` if a document was deleted, ``False`` if it did not
            exist or belonged to a different owner.
        """
        ref = self._doc_ref(contact_id)
        snapshot = await ref.get()
        if not snapshot.exists:
            return False
        if snapshot.to_dict().get("owner_id") != owner_id:
            return False
        await ref.delete()
        logger.info("contact_deleted", contact_id=str(contact_id), owner_id=owner_id)
        return True

    async def list_for_owner(self, owner_id: str) -> list[Contact]:
        """Return every contact in the collection owned by ``owner_id``.

        Requires a composite index on ``(owner_id)`` — single-field indexes
        are auto-created by Firestore.

        Args:
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            Matching contacts in arbitrary order (Firestore does not
            guarantee ordering without an explicit ``order_by``).
        """
        from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: PLC0415

        query = self.client.collection(self.collection_name).where(
            filter=FieldFilter("owner_id", "==", owner_id)
        )
        results: list[Contact] = []
        async for snapshot in query.stream():
            data = snapshot.to_dict()
            if data is not None:
                results.append(Contact.model_validate(data))
        return results

    async def list_page(
        self,
        owner_id: str,
        *,
        limit: int,
        cursor: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Contact], str | None]:
        """Return one page of contacts ordered by ``(full_name_lower, id)``.

        When ``q`` is unset the page is fetched directly with
        ``order_by + start_after + limit(N+1)`` so a single Firestore
        query yields the page and detects whether more pages remain.

        When ``q`` is set the same prefix-range filter is fanned out
        across ``full_name_lower``, ``preferred_name_lower``, and
        ``email_lower``. Each query returns at most a few hundred docs
        for any reasonably specific prefix; the union is deduped by
        ``id``, sorted in Python, and sliced to the requested page.

        Composite indexes required (declared in
        ``infra/firestore.indexes.json`` and applied on deploy):

        - ``(owner_id ASC, full_name_lower ASC)`` — used for the no-q
          path and for ``full_name_lower`` prefix search.
        - ``(owner_id ASC, preferred_name_lower ASC)`` — for prefix
          search on the optional preferred-name field.
        - ``(owner_id ASC, email_lower ASC)`` — for prefix search on the
          email field.

        Args:
            owner_id: Firebase ``uid`` of the caller.
            limit: Maximum items in the page.
            cursor: ``id`` of the last contact from the previous page,
                or ``None`` for the first page.
            q: Optional case-insensitive prefix.

        Returns:
            ``(items, next_cursor)``.
        """
        normalised = (q or "").strip().lower()
        if normalised:
            return await self._list_page_with_search(owner_id, limit, cursor, normalised)
        return await self._list_page_no_search(owner_id, limit, cursor)

    async def _list_page_no_search(
        self, owner_id: str, limit: int, cursor: str | None
    ) -> tuple[list[Contact], str | None]:
        """Single-query paged read sorted by ``(full_name_lower, id)``."""
        from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: PLC0415

        query = (
            self.client.collection(self.collection_name)
            .where(filter=FieldFilter("owner_id", "==", owner_id))
            .order_by("full_name_lower")
            .order_by("__name__")
        )
        if cursor is not None:
            cursor_snap = await self._doc_ref_str(cursor).get()
            if not cursor_snap.exists:
                # Cursor refers to a deleted/never-existed doc. Match the
                # in-memory adapter's behaviour: empty page, no next.
                return ([], None)
            query = query.start_after(cursor_snap)

        # Fetch one extra so we can tell whether more pages remain
        # without firing a second query.
        query = query.limit(limit + 1)
        items: list[Contact] = []
        async for snapshot in query.stream():
            data = snapshot.to_dict()
            if data is not None:
                items.append(Contact.model_validate(data))

        has_more = len(items) > limit
        page = items[:limit]
        next_cursor = str(page[-1].id) if has_more and page else None
        return (page, next_cursor)

    async def _list_page_with_search(
        self, owner_id: str, limit: int, cursor: str | None, q: str
    ) -> tuple[list[Contact], str | None]:
        """Fan-out prefix search → union → sort → slice."""
        merged = await self._search_merged(owner_id, q)
        merged.sort(key=lambda c: (c.full_name_lower, str(c.id)))
        start = 0
        if cursor is not None:
            for index, item in enumerate(merged):
                if str(item.id) == cursor:
                    start = index + 1
                    break
            else:
                return ([], None)
        page = merged[start : start + limit]
        next_cursor = str(page[-1].id) if page and start + limit < len(merged) else None
        return (page, next_cursor)

    async def count_for_owner(
        self,
        owner_id: str,
        *,
        q: str | None = None,
    ) -> int:
        """Count contacts owned by ``owner_id`` (optionally q-filtered).

        With no ``q``, uses Firestore's ``count()`` aggregate (~1
        billable query unit). With ``q`` set, falls back to the union
        used by :meth:`list_page` since the deduped count can't be
        derived from three independent ``count()`` aggregates.

        Args:
            owner_id: Firebase ``uid`` of the caller.
            q: Optional case-insensitive prefix.

        Returns:
            Total number of matching contacts.
        """
        from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: PLC0415

        normalised = (q or "").strip().lower()
        if not normalised:
            # ``Any`` cast: the SDK's aggregation type stubs are
            # incomplete (mypy thinks ``.get()`` is unbound), but the
            # runtime contract is well-documented.
            agg: Any = (
                self.client.collection(self.collection_name)
                .where(filter=FieldFilter("owner_id", "==", owner_id))
                .count()
            )
            result = await agg.get()
            # The aggregate returns ``[[AggregationResult]]``; pull out the
            # single integer.
            return int(result[0][0].value)
        merged = await self._search_merged(owner_id, normalised)
        return len(merged)

    async def _search_merged(self, owner_id: str, q: str) -> list[Contact]:
        r"""Run prefix queries on the three lowercase fields and dedupe by id.

        Uses Firestore's prefix-query idiom: ``where(field, ">=", q)`` AND
        ``where(field, "<", q + "")`` constrains results to keys
        starting with ``q`` (the high sentinel is the largest BMP
        codepoint, putting it after every plausible prefix continuation).

        Args:
            owner_id: Firebase ``uid`` of the caller.
            q: Already-trimmed, already-lowercased prefix.

        Returns:
            Deduped contacts (one per ``id``) in arbitrary order.
        """
        seen: dict[UUID, Contact] = {}
        for field in ("full_name_lower", "preferred_name_lower", "email_lower"):
            async for snapshot in self._prefix_query(owner_id, field, q).stream():
                data = snapshot.to_dict()
                if data is None:
                    continue
                contact = Contact.model_validate(data)
                seen[contact.id] = contact
        return list(seen.values())

    def _prefix_query(self, owner_id: str, field: str, q: str) -> Any:
        """Build the ``owner_id == X AND field PREFIX q`` query for one field."""
        from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: PLC0415

        # ```` is the largest BMP codepoint, used as the standard
        # Firestore prefix-query sentinel.
        return (
            self.client.collection(self.collection_name)
            .where(filter=FieldFilter("owner_id", "==", owner_id))
            .where(filter=FieldFilter(field, ">=", q))
            .where(filter=FieldFilter(field, "<", q + ""))
            .order_by(field)
        )

    def _doc_ref_str(self, contact_id: str) -> Any:
        """Document reference from a string id (used by cursor lookup)."""
        return self.client.collection(self.collection_name).document(contact_id)


class FirestoreCollectionRequestRepository:
    """Firestore-backed :class:`~birthday_tracker.services.CollectionRequestRepository`.

    Documents are keyed by request UUID. Token-hash lookups use a Firestore
    ``where`` query — for a personal-use app this stays cheap because the
    collection never grows large; if it ever does, add a composite index.

    Attributes:
        client: Injected :class:`google.cloud.firestore.AsyncClient`.
        collection_name: Name of the Firestore collection (overridable in
            integration tests for isolation).
    """

    def __init__(
        self,
        client: AsyncClient,
        collection_name: str = COLLECTION_REQUESTS_COLLECTION,
    ) -> None:
        """Build the repository.

        Args:
            client: Pre-built Firestore async client.
            collection_name: Collection name. Defaults to ``"collection_requests"``.
        """
        self.client = client
        self.collection_name = collection_name

    def _doc_ref(self, request_id: UUID) -> Any:
        """Document reference for ``request_id`` (typed as ``Any`` due to SDK stubs)."""
        return self.client.collection(self.collection_name).document(str(request_id))

    async def get(self, request_id: UUID, owner_id: str) -> CollectionRequest | None:
        """Fetch a request by UUID if owned by ``owner_id``.

        Args:
            request_id: Request UUID.
            owner_id: Firebase ``uid`` of the caller.

        Returns:
            The :class:`CollectionRequest`, or ``None`` on absence / owner
            mismatch.
        """
        snapshot = await self._doc_ref(request_id).get()
        if not snapshot.exists:
            return None
        request = CollectionRequest.model_validate(snapshot.to_dict())
        if request.owner_id != owner_id:
            return None
        return request

    async def get_by_token_hash(self, token_hash: str) -> CollectionRequest | None:
        """Fetch by issued-token hash. Intentionally not owner-scoped.

        Args:
            token_hash: Hex SHA-256 digest of the issued token.

        Returns:
            The :class:`CollectionRequest` or ``None`` if no match.
        """
        from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: PLC0415

        query = (
            self.client.collection(self.collection_name)
            .where(filter=FieldFilter("token_hash", "==", token_hash))
            .limit(1)
        )
        async for snapshot in query.stream():
            data = snapshot.to_dict()
            if data is not None:
                return CollectionRequest.model_validate(data)
        return None

    async def save(self, request: CollectionRequest) -> None:
        """Upsert ``request``.

        Args:
            request: Request to persist. The caller has already set
                :attr:`CollectionRequest.owner_id`.
        """
        await self._doc_ref(request.id).set(request.model_dump(mode="json"))
        logger.info(
            "collection_request_saved",
            request_id=str(request.id),
            owner_id=request.owner_id,
        )


class FirestoreUserRepository:
    """Firestore-backed :class:`~birthday_tracker.services.UserRepository`.

    User profiles are stored in ``users/{uid}`` so the document ID matches
    the Firebase Auth identifier directly.

    Attributes:
        client: Injected :class:`google.cloud.firestore.AsyncClient`.
        collection_name: Collection name (overridable in tests).
    """

    def __init__(
        self,
        client: AsyncClient,
        collection_name: str = USERS_COLLECTION,
    ) -> None:
        """Build the repository.

        Args:
            client: Pre-built Firestore async client.
            collection_name: Collection name. Defaults to ``"users"``.
        """
        self.client = client
        self.collection_name = collection_name

    def _doc_ref(self, user_id: str) -> Any:
        """Document reference for ``user_id``."""
        return self.client.collection(self.collection_name).document(user_id)

    async def get(self, user_id: str) -> User | None:
        """Fetch a user profile.

        Args:
            user_id: Firebase ``uid``.

        Returns:
            The :class:`User`, or ``None`` if the profile has not been
            created yet.
        """
        snapshot = await self._doc_ref(user_id).get()
        if not snapshot.exists:
            return None
        return User.model_validate(snapshot.to_dict())

    async def save(self, user: User) -> None:
        """Upsert ``user``.

        Args:
            user: User profile to persist.
        """
        await self._doc_ref(user.id).set(user.model_dump(mode="json"))
        logger.info("user_saved", user_id=user.id)

    async def list_all(self) -> list[User]:
        """Return every user profile.

        Returns:
            All profiles in arbitrary order.
        """
        results: list[User] = []
        async for snapshot in self.client.collection(self.collection_name).stream():
            data = snapshot.to_dict()
            if data is not None:
                results.append(User.model_validate(data))
        return results
