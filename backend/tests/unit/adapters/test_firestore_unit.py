"""Unit tests for FirestoreContactRepository edge cases.

These cover branches that are awkward to trigger against the real emulator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from birthday_tracker.adapters import FirestoreContactRepository
from tests._contracts.contact_repository import OWNER, make_contact


class _StreamingQuery:
    """Async iterable yielding mock snapshots."""

    def __init__(self, snapshots: list[Any]) -> None:
        self._snapshots = snapshots

    def stream(self) -> AsyncIterator[Any]:
        async def _gen() -> AsyncIterator[Any]:
            for snap in self._snapshots:
                yield snap

        return _gen()


class _FilterableCollection(_StreamingQuery):
    """Mock collection that also accepts ``.where(...)`` and returns itself."""

    def where(self, filter: Any) -> _FilterableCollection:  # noqa: A002, ARG002
        return self


@pytest.mark.unit
async def test_list_for_owner_skips_snapshots_with_no_data() -> None:
    """A snapshot whose ``to_dict()`` returns ``None`` is dropped silently.

    Firestore can theoretically yield a snapshot that has no underlying data
    (e.g. concurrently deleted between query and stream). This branch keeps
    the adapter robust without requiring callers to filter ``None`` themselves.
    """
    contact = make_contact()
    good_snap = MagicMock()
    good_snap.to_dict.return_value = contact.model_dump(mode="json")
    bad_snap = MagicMock()
    bad_snap.to_dict.return_value = None

    client = MagicMock()
    client.collection.return_value = _FilterableCollection([good_snap, bad_snap])

    repo = FirestoreContactRepository(client=client, collection_name="any")
    results = await repo.list_for_owner(OWNER)

    assert len(results) == 1
    assert results[0].id == contact.id


@pytest.mark.unit
async def test_get_returns_none_when_doc_missing() -> None:
    """Unit-only mirror of the integration test — guards the snapshot.exists branch."""
    snap = MagicMock()
    snap.exists = False
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=snap)
    collection = MagicMock()
    collection.document.return_value = doc_ref
    client = MagicMock()
    client.collection.return_value = collection

    repo = FirestoreContactRepository(client=client, collection_name="any")
    assert await repo.get(make_contact().id, OWNER) is None


@pytest.mark.unit
async def test_get_returns_none_when_owner_mismatch() -> None:
    """A document owned by a different user must look like absence."""
    contact = make_contact(owner_id="someone-else")
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = contact.model_dump(mode="json")
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=snap)
    collection = MagicMock()
    collection.document.return_value = doc_ref
    client = MagicMock()
    client.collection.return_value = collection

    repo = FirestoreContactRepository(client=client, collection_name="any")
    assert await repo.get(contact.id, OWNER) is None


@pytest.mark.unit
async def test_delete_returns_false_when_owner_mismatch() -> None:
    """Deleting another tenant's document must be a no-op."""
    contact = make_contact(owner_id="someone-else")
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = contact.model_dump(mode="json")
    doc_ref = MagicMock()
    doc_ref.get = AsyncMock(return_value=snap)
    doc_ref.delete = AsyncMock()
    collection = MagicMock()
    collection.document.return_value = doc_ref
    client = MagicMock()
    client.collection.return_value = collection

    repo = FirestoreContactRepository(client=client, collection_name="any")
    assert await repo.delete(contact.id, OWNER) is False
    doc_ref.delete.assert_not_awaited()
