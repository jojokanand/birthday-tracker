"""Pytest fixtures shared across unit and integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.core.config import AppEnv, Settings, get_settings
from birthday_tracker.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Return a deterministic test :class:`Settings` instance.

    Avoids reading the developer's local ``.env`` file by constructing the
    settings object directly with explicit values.
    """
    return Settings(app_env=AppEnv.development, log_level="DEBUG", gcp_project_id="test-project")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Yield a :class:`fastapi.testclient.TestClient` bound to a fresh app.

    Clears the cached :func:`get_settings` so the test ``Settings`` actually
    take effect for any code path that reads them via dependency injection.
    """
    get_settings.cache_clear()
    app = create_app(settings=settings)
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
