"""Fixtures for integration tests.

Integration tests require external services (Firestore emulator, etc.). When
those services are not available — e.g. on a developer machine without the
emulator running — the affected tests are skipped with a clear message rather
than failing.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest

from birthday_tracker.adapters import (
    FirestoreContactRepository,
    build_async_client,
)

EMULATOR_ENV = "FIRESTORE_EMULATOR_HOST"
TEST_PROJECT = "birthday-tracker-test"


def _emulator_running() -> bool:
    """Return ``True`` when the Firestore emulator host env var is set."""
    return bool(os.environ.get(EMULATOR_ENV))


@pytest.fixture
async def firestore_repo() -> AsyncIterator[FirestoreContactRepository]:
    """Yield a :class:`FirestoreContactRepository` pointed at a unique collection.

    Skips the test when ``FIRESTORE_EMULATOR_HOST`` is not set, so developers
    who don't have the emulator running locally aren't blocked. The collection
    name includes a UUID suffix so parallel tests do not collide; on teardown
    every document in the collection is deleted.

    Yields:
        A repository ready for use. The collection is empty at fixture entry
        and cleaned up on exit.
    """
    if not _emulator_running():
        pytest.skip(f"{EMULATOR_ENV} is not set — start the Firestore emulator")

    client = build_async_client(project_id=TEST_PROJECT)
    collection = f"contacts-test-{uuid.uuid4().hex}"
    repo = FirestoreContactRepository(client=client, collection_name=collection)

    try:
        yield repo
    finally:
        # Best-effort cleanup: delete everything in this test's collection.
        async for snapshot in client.collection(collection).stream():
            await snapshot.reference.delete()
