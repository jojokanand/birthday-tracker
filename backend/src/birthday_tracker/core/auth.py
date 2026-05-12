"""Authentication primitives.

The owner-side endpoints expect a Firebase Auth ID token in the
``Authorization: Bearer <id_token>`` header. The token is verified via
``firebase_admin.auth.verify_id_token`` which checks the signature, the
expiry, and that the issuer is the project's Firebase Auth tenant.

In development mode (``APP_ENV=development``) verification is bypassed
and a deterministic dev :class:`Identity` is returned so the dashboard
remains usable without a Firebase project — matching the existing pattern
of in-memory repositories in :mod:`birthday_tracker.main`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    """The authenticated user making a request.

    Attributes:
        user_id: Stable identifier — the Firebase Auth ``uid``. In dev mode
            this is a fixed sentinel (``"dev-user"``) so test data is
            stable across runs.
        email: Email address Firebase verified for this user.
    """

    user_id: str
    email: str


_DEV_IDENTITY = Identity(user_id="dev-user", email="dev@example.com")

_firebase_init_lock = threading.Lock()
_firebase_initialized = False


def dev_identity() -> Identity:
    """Return the fixed development identity.

    Returns:
        A static :class:`Identity` used when ``APP_ENV=development``.
    """
    return _DEV_IDENTITY


def _ensure_firebase_initialized() -> None:
    """Initialize the Firebase Admin SDK once per process.

    The SDK picks up Application Default Credentials automatically when
    running on GCP (Cloud Run, GKE, etc.), so no explicit credentials are
    needed in production. Locally, this requires ``GOOGLE_APPLICATION_CREDENTIALS``
    pointing at a service-account key file — but we never reach this code
    in dev mode anyway.

    Raises:
        RuntimeError: If initialization fails. Propagates the underlying
            cause so it surfaces in logs.
    """
    global _firebase_initialized
    if _firebase_initialized:
        return
    with _firebase_init_lock:
        if _firebase_initialized:  # double-checked after acquiring the lock
            return
        import firebase_admin  # noqa: PLC0415

        try:
            firebase_admin.get_app()
        except ValueError:
            # No default app yet — initialize one with ADC.
            firebase_admin.initialize_app()
        _firebase_initialized = True


def verify_firebase_id_token(token: str) -> Identity:
    """Verify a Firebase ID token and return the resulting :class:`Identity`.

    Args:
        token: The raw JWT from the ``Authorization`` header (the
            ``"Bearer "`` prefix has already been stripped).

    Returns:
        An :class:`Identity` populated from the token's ``uid`` and
        ``email`` claims.

    Raises:
        ValueError: If the token is invalid, expired, has the wrong
            issuer/audience, or is missing required claims. The auth
            dependency translates this into an HTTP 401.
    """
    _ensure_firebase_initialized()
    from firebase_admin import auth as fb_auth  # noqa: PLC0415

    try:
        decoded: dict[str, object] = fb_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001 — SDK can raise many types
        raise ValueError(f"invalid Firebase ID token: {exc}") from exc

    uid = decoded.get("uid")
    email = decoded.get("email")
    if not isinstance(uid, str) or not uid:
        raise ValueError("token is missing 'uid' claim")
    if not isinstance(email, str) or not email:
        raise ValueError("token is missing 'email' claim")
    return Identity(user_id=uid, email=email)
