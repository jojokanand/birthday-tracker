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
