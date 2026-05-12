"""Unit tests for the ``/me`` (user profile) router and the ``require_user``
auth dependency.

The auth dependency in development mode bypasses Firebase entirely and
returns the fixed dev identity; production-mode tests patch
:func:`birthday_tracker.core.auth.verify_firebase_id_token` to control
the resolved :class:`Identity`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.adapters import InMemoryUserRepository
from birthday_tracker.api.dependencies import get_user_repository
from birthday_tracker.core.auth import Identity
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app

DEV_OWNER = "dev-user"
DEV_EMAIL = "dev@example.com"


def _build_dev_client(repo: InMemoryUserRepository) -> TestClient:
    """A TestClient with the dev-mode auth bypass active."""
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_user_repository] = lambda: repo
    return TestClient(app)


def _build_prod_client(repo: InMemoryUserRepository) -> TestClient:
    """A TestClient with production-mode auth (real verifier is patched per-test)."""
    get_settings_dep.cache_clear()
    app = create_app(
        settings=Settings(
            app_env=AppEnv.production,
            log_level="ERROR",
            form_token_secret="not-used-here-but-required",
            public_base_url="https://example.test",
        )
    )
    app.dependency_overrides[get_user_repository] = lambda: repo
    return TestClient(app)


# ---------------------------------------------------------------------------
# /me with dev-mode bypass
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_get_me_creates_profile_on_first_call() -> None:
    repo = InMemoryUserRepository()
    client = _build_dev_client(repo)

    resp = client.get("/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == DEV_OWNER
    assert body["email"] == DEV_EMAIL
    # Profile is now persisted.
    stored = await repo.get(DEV_OWNER)
    assert stored is not None


@pytest.mark.unit
async def test_get_me_returns_stored_profile_on_subsequent_calls() -> None:
    repo = InMemoryUserRepository()
    client = _build_dev_client(repo)

    first = client.get("/me").json()
    second = client.get("/me").json()
    assert first["id"] == second["id"]
    assert first["created_at"] == second["created_at"]  # not re-created


@pytest.mark.unit
async def test_put_me_updates_digest_settings() -> None:
    repo = InMemoryUserRepository()
    client = _build_dev_client(repo)

    resp = client.put(
        "/me",
        json={
            "digest_owner_email": "shared@example.com",
            "digest_timezone": "America/New_York",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["digest_owner_email"] == "shared@example.com"
    assert body["digest_timezone"] == "America/New_York"

    stored = await repo.get(DEV_OWNER)
    assert stored is not None
    assert stored.digest_owner_email == "shared@example.com"


# ---------------------------------------------------------------------------
# Production-mode auth path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prod_missing_bearer_returns_401() -> None:
    """No ``Authorization`` header → 401."""
    repo = InMemoryUserRepository()
    client = _build_prod_client(repo)
    resp = client.get("/me")
    assert resp.status_code == 401


@pytest.mark.unit
def test_prod_invalid_token_returns_401() -> None:
    """Forged / unparseable token → 401."""
    repo = InMemoryUserRepository()
    client = _build_prod_client(repo)

    def _boom(*_: Any, **__: Any) -> None:
        raise ValueError("bad token")

    with patch(
        "birthday_tracker.api.dependencies.verify_firebase_id_token",
        side_effect=_boom,
    ):
        resp = client.get("/me", headers={"Authorization": "Bearer junk"})
    assert resp.status_code == 401


@pytest.mark.unit
def test_prod_valid_token_returns_profile() -> None:
    """A valid token resolves to an :class:`Identity` and yields a 200 profile."""
    repo = InMemoryUserRepository()
    client = _build_prod_client(repo)

    ident = Identity(user_id="firebase-uid-123", email="real@example.com")
    with patch(
        "birthday_tracker.api.dependencies.verify_firebase_id_token",
        return_value=ident,
    ):
        resp = client.get("/me", headers={"Authorization": "Bearer real-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "firebase-uid-123"
    assert body["email"] == "real@example.com"
