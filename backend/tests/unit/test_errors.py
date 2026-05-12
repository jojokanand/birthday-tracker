"""Unit tests for the RFC 7807 error handling layer."""

from __future__ import annotations

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from birthday_tracker.api.errors import PROBLEM_JSON, APIError
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app

_extra_router = APIRouter()


@_extra_router.get("/raise-api-error")
def _raise_api_error() -> None:
    """Test-only route that raises an APIError so the handler runs."""
    raise APIError(
        status_code=409,
        title="Conflict",
        detail="Already exists",
        type_uri="https://example.com/errors/conflict",
    )


@_extra_router.get("/raise-unhandled")
def _raise_unhandled() -> None:
    """Test-only route that raises a generic Exception."""
    raise RuntimeError("boom")


@pytest.fixture
def app_client() -> TestClient:
    """Build a TestClient with the test-only error routes attached."""
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.include_router(_extra_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_api_error_returns_problem_json(app_client: TestClient) -> None:
    response = app_client.get("/raise-api-error")
    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    body = response.json()
    assert body == {
        "type": "https://example.com/errors/conflict",
        "title": "Conflict",
        "status": 409,
        "detail": "Already exists",
        "instance": "/raise-api-error",
    }


@pytest.mark.unit
def test_unknown_route_returns_problem_json_404(app_client: TestClient) -> None:
    response = app_client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    body = response.json()
    assert body["status"] == 404
    assert body["instance"] == "/does-not-exist"


@pytest.mark.unit
def test_unhandled_exception_returns_500(app_client: TestClient) -> None:
    response = app_client.get("/raise-unhandled")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    body = response.json()
    assert body["title"] == "Internal server error"
    # Must NOT leak the underlying exception message.
    assert "boom" not in str(body)
