"""Unit tests for the /ready endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.core.health import ReadinessResult


class _FakeAsyncCollections:
    """Async iterable that yields a single sentinel — proves the ping loop ran."""

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[Any]:
        yield object()


class _EmptyAsyncCollections:
    """Async iterable that yields nothing — covers the empty-iter branch."""

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[Any]:
        if False:  # pragma: no cover - generator must be async; never yields
            yield


class _FakeFirestoreClient:
    """Minimal stand-in for `google.cloud.firestore.AsyncClient`."""

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def collections(self) -> _FakeAsyncCollections:
        return _FakeAsyncCollections()


class _EmptyFirestoreClient:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def collections(self) -> _EmptyAsyncCollections:
        return _EmptyAsyncCollections()


class _FailingFirestoreClient:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def collections(self) -> Any:
        raise RuntimeError("connection refused")


@pytest.mark.unit
def test_ready_returns_200_when_firestore_reachable(client: TestClient) -> None:
    with patch("google.cloud.firestore.AsyncClient", _FakeFirestoreClient):
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ready", "firestore": "ok"}


@pytest.mark.unit
def test_ready_returns_503_when_firestore_unreachable(client: TestClient) -> None:
    with patch("google.cloud.firestore.AsyncClient", _FailingFirestoreClient):
        response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert "connection refused" in body["firestore"]


@pytest.mark.unit
def test_ready_returns_200_when_collections_iter_is_empty(client: TestClient) -> None:
    """An empty Firestore project still proves reachability — covers the no-break branch."""
    with patch("google.cloud.firestore.AsyncClient", _EmptyFirestoreClient):
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "firestore": "ok"}


@pytest.mark.unit
async def test_check_firestore_returns_result_on_failure() -> None:
    """Direct unit test on the helper — bypasses HTTP."""
    from birthday_tracker.core import health

    with patch("google.cloud.firestore.AsyncClient", _FailingFirestoreClient):
        result = await health.check_firestore(project_id="test")
    assert isinstance(result, ReadinessResult)
    assert result.ok is False
    assert result.detail is not None
