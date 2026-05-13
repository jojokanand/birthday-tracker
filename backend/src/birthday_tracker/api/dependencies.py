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
    GmailNotifier,
    TwilioNotifier,
    build_async_client,
    build_gmail_service,
    build_twilio_client,
    load_gmail_credentials,
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
from birthday_tracker.services.notifiers import EmailNotifier, SmsNotifier


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


def get_sms_notifier(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> SmsNotifier | None:
    """Return the configured SMS notifier, or ``None`` when Twilio is unset.

    Tests override this to inject a fake; the live wiring constructs a
    :class:`TwilioNotifier` lazily so the app boots even without Twilio
    credentials (the dashboard half of the app doesn't need them).

    Args:
        request: Incoming request — checked for a test-time override on
            ``app.state.sms_notifier``.
        settings: Process settings (Twilio account SID / auth token /
            from-number).

    Returns:
        A :class:`TwilioNotifier` when all three Twilio settings are
        non-empty, else ``None``.
    """
    override = getattr(request.app.state, "sms_notifier", None)
    if override is not None:
        return override  # type: ignore[no-any-return]
    if not (
        settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
    ):
        return None
    client = build_twilio_client(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
    )
    return TwilioNotifier(client=client, from_number=settings.twilio_from_number)


def get_email_notifier(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> EmailNotifier | None:
    """Return the configured email notifier, or ``None`` when Gmail is unset.

    Production loads credentials from the raw JSON in the
    ``GMAIL_OAUTH_TOKEN`` env var (mounted by Cloud Run from Secret
    Manager); local dev can use ``gmail_oauth_token_path`` instead.

    Args:
        request: Incoming request — checked for a test-time override on
            ``app.state.email_notifier``.
        settings: Process settings (Gmail OAuth token + from-address).

    Returns:
        A :class:`GmailNotifier` when ``gmail_from_address`` and one of
        ``gmail_oauth_token`` / ``gmail_oauth_token_path`` are set,
        else ``None``.
    """
    override = getattr(request.app.state, "email_notifier", None)
    if override is not None:
        return override  # type: ignore[no-any-return]
    if not settings.gmail_from_address:
        return None
    if not (settings.gmail_oauth_token or settings.gmail_oauth_token_path):
        return None
    creds = load_gmail_credentials(
        client_secrets_path=settings.gmail_oauth_client_secrets_path,
        token_path=settings.gmail_oauth_token_path,
        token_json=settings.gmail_oauth_token,
    )
    service = build_gmail_service(creds)
    return GmailNotifier(service=service, from_address=settings.gmail_from_address)


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
