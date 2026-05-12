"""Application configuration loaded from environment variables.

Uses :mod:`pydantic_settings` so values are validated at startup and typed
throughout the codebase. The :func:`get_settings` accessor is cached so repeated
calls return the same object — this is what FastAPI dependencies use.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Deployment environment for the API."""

    development = "development"
    staging = "staging"
    production = "production"


class Settings(BaseSettings):
    """Strongly-typed runtime settings sourced from the environment.

    Attributes:
        app_env: Which environment the API is running in. Drives feature flags
            and stricter checks in production.
        log_level: Root logger level (e.g. ``INFO``, ``DEBUG``).
        gcp_project_id: GCP project ID used for Firestore and Secret Manager.
        firestore_emulator_host: When set, the Firestore client points at the
            local emulator instead of the real service. Used for integration
            tests and local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.development
    log_level: str = "INFO"

    gcp_project_id: str = Field(default="", description="GCP project ID")
    firestore_emulator_host: str = Field(
        default="",
        description="Set to host:port to redirect Firestore client to the emulator.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Returns:
        The process-wide :class:`Settings` instance. Cached so repeated calls
        (typical with FastAPI's ``Depends``) do not re-parse the environment.
    """
    return Settings()
