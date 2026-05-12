"""Unit tests for the configuration module."""

from __future__ import annotations

import pytest

from birthday_tracker.core.config import AppEnv, Settings


@pytest.mark.unit
def test_defaults_are_development() -> None:
    """A bare Settings() defaults to the development environment."""
    settings = Settings(_env_file=None)
    assert settings.app_env == AppEnv.development
    assert settings.log_level == "INFO"


@pytest.mark.unit
def test_env_override_via_kwargs() -> None:
    """Settings accepts explicit kwargs (used by test fixtures)."""
    settings = Settings(app_env=AppEnv.production, log_level="ERROR")
    assert settings.app_env is AppEnv.production
    assert settings.log_level == "ERROR"
