"""FastAPI application entry point.

The :func:`create_app` factory is the single source of truth for wiring routers,
middleware, and lifespan handlers. Tests import it directly so they never depend
on a module-level singleton.
"""

from __future__ import annotations

from fastapi import FastAPI

from birthday_tracker import __version__
from birthday_tracker.api import health
from birthday_tracker.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        settings: Optional pre-built settings object. When ``None`` (the default),
            settings are loaded from the environment via
            :func:`birthday_tracker.core.config.get_settings`. Tests pass a
            custom ``Settings`` instance to avoid touching real env vars.

    Returns:
        A fully wired :class:`fastapi.FastAPI` instance ready to be served by an
        ASGI server such as Uvicorn.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="Birthday Tracker API",
        version=__version__,
        description=(
            "Backend for the Birthday Tracker. Manages contacts, collection "
            "requests, and outbound SMS/email notifications."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Stash settings on the app for downstream access via dependency injection.
    app.state.settings = settings

    app.include_router(health.router)
    return app


# Module-level app for `uvicorn birthday_tracker.main:app`.
app = create_app()
