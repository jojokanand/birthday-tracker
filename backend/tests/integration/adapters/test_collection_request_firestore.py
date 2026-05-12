"""Integration tests for :class:`FirestoreCollectionRequestRepository`.

Requires the Firestore emulator (``FIRESTORE_EMULATOR_HOST`` must be set).
Tests are skipped automatically when the emulator is not running.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
from collections.abc import AsyncIterator

import pytest

from birthday_tracker.adapters import (
    FirestoreCollectionRequestRepository,
    build_async_client,
)
from birthday_tracker.models import Channel, CollectionRequest

EMULATOR_ENV = "FIRESTORE_EMULATOR_HOST"
TEST_PROJECT = "birthday-tracker-test"


@pytest.fixture
async def request_repo() -> AsyncIterator[FirestoreCollectionRequestRepository]:
    """Yield a :class:`FirestoreCollectionRequestRepository` in a unique collection.

    Skips the test when ``FIRESTORE_EMULATOR_HOST`` is not set.
    The collection is cleaned up on exit.

    Yields:
        An empty repository backed by the Firestore emulator.
    """
    if not os.environ.get(EMULATOR_ENV):
        pytest.skip(f"{EMULATOR_ENV} is not set — start the Firestore emulator")

    client = build_async_client(project_id=TEST_PROJECT)
    collection = f"collection-requests-test-{uuid.uuid4().hex}"
    repo = FirestoreCollectionRequestRepository(client=client, collection_name=collection)

    try:
        yield repo
    finally:
        async for snapshot in client.collection(collection).stream():
            await snapshot.reference.delete()


def _make_request(
    contact_id: uuid.UUID | None = None,
    channel: Channel = Channel.email,
    destination: str = "ada@example.com",
    token_hash: str = "a" * 64,
    expires_at: dt.datetime | None = None,
    fulfilled_at: dt.datetime | None = None,
) -> CollectionRequest:
    """Build a minimal :class:`CollectionRequest` for testing."""
    return CollectionRequest(
        contact_id=contact_id or uuid.uuid4(),
        channel=channel,
        destination=destination,
        token_hash=token_hash,
        expires_at=expires_at or dt.datetime.now(dt.UTC) + dt.timedelta(days=7),
        fulfilled_at=fulfilled_at,
    )


@pytest.mark.integration
async def test_get_missing(request_repo: FirestoreCollectionRequestRepository) -> None:
    """get() returns None for an unknown UUID."""
    result = await request_repo.get(uuid.uuid4())
    assert result is None


@pytest.mark.integration
async def test_save_and_get_roundtrip(request_repo: FirestoreCollectionRequestRepository) -> None:
    """save() persists a request that get() can retrieve with equal fields."""
    req = _make_request()
    await request_repo.save(req)

    retrieved = await request_repo.get(req.id)
    assert retrieved is not None
    assert retrieved.id == req.id
    assert retrieved.contact_id == req.contact_id
    assert retrieved.channel == req.channel
    assert retrieved.token_hash == req.token_hash


@pytest.mark.integration
async def test_save_replaces_existing(request_repo: FirestoreCollectionRequestRepository) -> None:
    """A second save() with the same id overwrites the stored document."""
    req = _make_request()
    await request_repo.save(req)

    updated = req.model_copy(update={"destination": "updated@example.com"})
    await request_repo.save(updated)

    retrieved = await request_repo.get(req.id)
    assert retrieved is not None
    assert retrieved.destination == "updated@example.com"


@pytest.mark.integration
async def test_get_by_token_hash_returns_match(
    request_repo: FirestoreCollectionRequestRepository,
) -> None:
    """get_by_token_hash() returns the request with a matching hash."""
    req = _make_request(token_hash="b" * 64)
    await request_repo.save(req)

    found = await request_repo.get_by_token_hash("b" * 64)
    assert found is not None
    assert found.id == req.id


@pytest.mark.integration
async def test_get_by_token_hash_returns_none_for_unknown(
    request_repo: FirestoreCollectionRequestRepository,
) -> None:
    """get_by_token_hash() returns None when no matching document exists."""
    result = await request_repo.get_by_token_hash("c" * 64)
    assert result is None


@pytest.mark.integration
async def test_fulfilled_at_round_trips(request_repo: FirestoreCollectionRequestRepository) -> None:
    """fulfilled_at is persisted and retrieved accurately (UTC, sub-second not required)."""
    fulfilled = dt.datetime(2025, 6, 15, 12, 0, 0, tzinfo=dt.UTC)
    req = _make_request(fulfilled_at=fulfilled)
    await request_repo.save(req)

    retrieved = await request_repo.get(req.id)
    assert retrieved is not None
    assert retrieved.fulfilled_at is not None
    assert retrieved.fulfilled_at.replace(microsecond=0) == fulfilled.replace(microsecond=0)
