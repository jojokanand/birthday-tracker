"""FastAPI application entry point.

The :func:`create_app` factory is the single source of truth for wiring routers,
middleware, exception handlers, and lifespan handlers. Tests import it directly
so they never depend on a module-level singleton.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from birthday_tracker import __version__
from birthday_tracker.api import (
    collection_requests,
    contacts,
    digest,
    errors,
    form,
    health,
    ready,
    users,
)
from birthday_tracker.core.config import AppEnv, Settings, get_settings
from birthday_tracker.core.logging import configure_logging, get_logger
from birthday_tracker.core.rate_limit import RateLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        settings: Optional pre-built settings object. When ``None`` (the default),
            settings are loaded from the environment via
            :func:`birthday_tracker.core.config.get_settings`. Tests pass a
            custom :class:`Settings` instance to avoid touching real env vars.

    Returns:
        A fully wired :class:`fastapi.FastAPI` instance ready to be served by an
        ASGI server such as Uvicorn.
    """
    settings = settings or get_settings()
    configure_logging(level=settings.log_level)
    logger = get_logger(__name__)

    app = FastAPI(
        title="Birthday Genie API",
        version=__version__,
        description=(
            "Backend for Birthday Genie. Manages contacts, collection "
            "requests, and outbound SMS/email notifications."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Stash settings + shared singletons on the app for downstream DI.
    app.state.settings = settings
    app.state.form_rate_limiter = RateLimiter(
        max_per_window=settings.form_rate_limit_per_minute,
        window_seconds=60.0,
    )

    # In development mode, use in-memory repositories so the server starts
    # without GCP credentials.  The same instances are shared across all
    # requests, giving request-level persistence for local testing and E2E.
    if settings.app_env == AppEnv.development:
        from birthday_tracker.adapters import (  # noqa: PLC0415
            InMemoryCollectionRequestRepository,
            InMemoryContactRepository,
            InMemoryUserRepository,
        )

        app.state.contact_repo = InMemoryContactRepository()
        app.state.collection_request_repo = InMemoryCollectionRequestRepository()
        app.state.user_repo = InMemoryUserRepository()
    else:
        app.state.contact_repo = None
        app.state.collection_request_repo = None
        app.state.user_repo = None

    # Allow the frontend to make cross-origin requests from the browser.
    # In development/staging any origin is permitted; in production only the
    # dashboard origin is allowed so browsers enforce the restriction.
    cors_origins = ["*"] if settings.app_env != AppEnv.production else [settings.public_base_url]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    errors.install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(ready.router)
    app.include_router(contacts.router)
    app.include_router(collection_requests.router)
    app.include_router(form.router)
    app.include_router(digest.router)
    app.include_router(users.router)

    logger.info("app_created", env=settings.app_env, version=__version__)
    return app


# Module-level app for `uvicorn birthday_tracker.main:app`.
app = create_app()
