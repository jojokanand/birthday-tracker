"""Unit tests for the health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from birthday_tracker import __version__


@pytest.mark.unit
def test_health_returns_ok(client: TestClient) -> None:
    """`GET /health` returns 200 with status=ok and the package version."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "version": __version__}


@pytest.mark.unit
def test_openapi_schema_published(client: TestClient) -> None:
    """The FastAPI app publishes an OpenAPI schema with the health route."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/health" in schema["paths"]
