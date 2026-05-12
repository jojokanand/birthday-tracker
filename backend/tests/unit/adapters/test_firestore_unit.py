"""Unit tests for FirestoreContactRepository edge cases.

These cover branches that are awkward to trigger against the real emulator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from birthday_tracker.adapters import FirestoreContactRepository
from tests._contracts.contact_repository import make_contact


class _StreamingCollection:
    """Async iterable yielding two mock snapshots — one with data, one with None."""

    def __init__(self, snapshots: list[Any]) -> None:
        self._snapshots = snapshots

    def stream(self) -> AsyncIterator[Any]:
        async def _gen() -> AsyncIterator[Any]:
            for snap in self._snapshots:
                yield snap

        return _gen()


@pytest.mark.unit
async def test_list_all_skips_snapshots_with_no_data() -> None:
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
    client.collection.return_value = _StreamingCollection([good_snap, bad_snap])

    repo = FirestoreContactRepository(client=client, collection_name="any")
    results = await repo.list_all()

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
    assert await repo.get(make_contact().id) is None
