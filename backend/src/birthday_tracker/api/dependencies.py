"""FastAPI dependency providers.

Wire concrete adapters and services together. Centralized so routes never
import adapters directly — they only depend on protocols, with the wiring
swappable in tests via ``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from birthday_tracker.adapters import (
    FirestoreCollectionRequestRepository,
    FirestoreContactRepository,
    FirestoreUserRepository,
    build_async_client,
)
from birthday_tracker.core.auth import Identity, dev_identity, verify_firebase_id_token
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.rate_limit import RateLimiter
from birthday_tracker.services import (
    CollectionRequestRepository,
    ContactRepository,
    UserRepository,
)
from birthday_tracker.services.collection_requests import CollectionRequestService


def get_app_settings(request: Request) -> Settings:
    """Return the :class:`Settings` instance attached to the running app.

    Args:
        request: Incoming request — FastAPI injects this; ``request.app.state``
            holds the settings stashed by :func:`birthday_tracker.main.create_app`.

    Returns:
        The process-wide :class:`Settings`.
    """
    settings: Settings = request.app.state.settings
    return settings


def get_contact_repository(
    request: Request,
) -> ContactRepository:
    """Return the active :class:`ContactRepository`.

    In development mode the app stores a singleton
    :class:`~birthday_tracker.adapters.InMemoryContactRepository` on
    ``app.state`` so the server works without GCP credentials.  In staging
    and production a new :class:`FirestoreContactRepository` is built per
    request.

    Tests override this dependency via ``app.dependency_overrides``.

    Args:
        request: Incoming request; the repo may live on ``request.app.state``.

    Returns:
        A concrete :class:`ContactRepository`.
    """
    if request.app.state.contact_repo is not None:
        return request.app.state.contact_repo  # type: ignore[no-any-return]
    settings: Settings = request.app.state.settings
    client = build_async_client(project_id=settings.gcp_project_id)
    return FirestoreContactRepository(client=client)


def get_collection_request_repository(
    request: Request,
) -> CollectionRequestRepository:
    """Return the active :class:`CollectionRequestRepository`.

    Mirrors :func:`get_contact_repository` — uses the in-memory singleton in
    development, Firestore otherwise.

    Args:
        request: Incoming request.

    Returns:
        A concrete :class:`CollectionRequestRepository`.
    """
    if request.app.state.collection_request_repo is not None:
        return request.app.state.collection_request_repo  # type: ignore[no-any-return]
    settings: Settings = request.app.state.settings
    client = build_async_client(project_id=settings.gcp_project_id)
    return FirestoreCollectionRequestRepository(client=client)


def get_user_repository(
    request: Request,
) -> UserRepository:
    """Return the active :class:`UserRepository`.

    Same in-memory-vs-Firestore pattern as the other repos.

    Args:
        request: Incoming request.

    Returns:
        A concrete :class:`UserRepository`.
    """
    if request.app.state.user_repo is not None:
        return request.app.state.user_repo  # type: ignore[no-any-return]
    settings: Settings = request.app.state.settings
    client = build_async_client(project_id=settings.gcp_project_id)
    return FirestoreUserRepository(client=client)


def get_collection_request_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
    contacts: Annotated[ContactRepository, Depends(get_contact_repository)],
    requests: Annotated[
        CollectionRequestRepository,
        Depends(get_collection_request_repository),
    ],
) -> CollectionRequestService:
    """Construct the :class:`CollectionRequestService`.

    Args:
        settings: Process settings (token secret, TTL, public URL).
        contacts: Contact repository.
        requests: Collection-request repository.

    Returns:
        A configured :class:`CollectionRequestService`.
    """
    return CollectionRequestService(
        contacts=contacts,
        requests=requests,
        token_secret=settings.form_token_secret,
        token_ttl_seconds=settings.form_token_ttl_seconds,
        public_base_url=settings.public_base_url,
    )


def get_form_rate_limiter(request: Request) -> RateLimiter:
    """Return the singleton :class:`RateLimiter` attached to the app.

    Args:
        request: Incoming request; the limiter lives on ``app.state``
            so it is shared across all requests served by this process.

    Returns:
        The shared :class:`RateLimiter`.
    """
    limiter: RateLimiter = request.app.state.form_rate_limiter
    return limiter


# --- Authentication --------------------------------------------------------


def require_user(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str, Header()] = "",
) -> Identity:
    """Resolve the authenticated user for owner-side endpoints.

    In ``APP_ENV=development`` the check is bypassed and a fixed dev
    identity is returned, so the dashboard works without a real Firebase
    project. In any other environment a valid Firebase ID token is
    required in the ``Authorization: Bearer <token>`` header.

    Args:
        settings: Process settings (used to choose dev-bypass vs real verify).
        authorization: ``Authorization`` header value, injected by FastAPI.

    Returns:
        The :class:`Identity` representing the caller.

    Raises:
        HTTPException: 401 when the token is absent, malformed, or fails
            Firebase verification.
    """
    if settings.app_env == AppEnv.development:
        return dev_identity()

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("bearer ") :]
    try:
        return verify_firebase_id_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
