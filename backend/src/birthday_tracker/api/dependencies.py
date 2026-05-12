"""FastAPI dependency providers.

Wire concrete adapters and services together. Centralized so routes never
import adapters directly — they only depend on protocols, with the wiring
swappable in tests via ``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from birthday_tracker.adapters import (
    FirestoreCollectionRequestRepository,
    FirestoreContactRepository,
    build_async_client,
)
from birthday_tracker.core.config import Settings
from birthday_tracker.core.rate_limit import RateLimiter
from birthday_tracker.services import (
    CollectionRequestRepository,
    ContactRepository,
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
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ContactRepository:
    """Build the production :class:`ContactRepository` (Firestore).

    Tests override this dependency with an in-memory repository.

    Args:
        settings: Process settings (project ID, emulator host).

    Returns:
        A :class:`FirestoreContactRepository` ready for I/O.
    """
    client = build_async_client(project_id=settings.gcp_project_id)
    return FirestoreContactRepository(client=client)


def get_collection_request_repository(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> CollectionRequestRepository:
    """Build the production :class:`CollectionRequestRepository` (Firestore).

    Args:
        settings: Process settings.

    Returns:
        A :class:`FirestoreCollectionRequestRepository`.
    """
    client = build_async_client(project_id=settings.gcp_project_id)
    return FirestoreCollectionRequestRepository(client=client)


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


# --- Auth placeholder -------------------------------------------------------
# Real auth lands in issue #7 (GCP IAM / Identity-Aware Proxy). For now this
# dependency exists so the route signature already declares it; swap the body
# for a real check once auth is wired.

OwnerIdentity = str


def require_owner() -> Callable[[], OwnerIdentity]:
    """Return a dependency that yields the authenticated owner identity.

    Returns:
        A callable usable with ``Depends(require_owner())``. Currently a
        no-op stand-in; replace in issue #7.
    """

    def _identity() -> OwnerIdentity:
        # TODO(#7): replace with real auth check (IAP header / service account).
        return "owner"

    return _identity
