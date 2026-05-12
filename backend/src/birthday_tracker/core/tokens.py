"""HMAC-signed, time-boxed form tokens.

Format::

    base64url(payload_json) + "." + base64url(hmac_sha256(payload_json, secret))

The payload is a small JSON object — currently only ``request_id`` and ``exp``
(unix-second expiry). Tokens are stateless: verification needs only the
secret, which means revocation has to happen at the application layer (we
mark the :class:`CollectionRequest` as fulfilled after the first successful
submission so the same token can't be used twice).

Design notes:

- We keep the payload tiny so the token fits in a URL without truncation.
- We store the SHA-256 hash of every issued token on the
  :class:`CollectionRequest` so a leak of the database alone can't be
  replayed without also leaking the secret.
- Signature comparison uses :func:`hmac.compare_digest` to avoid timing
  attacks.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from uuid import UUID

_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_\-]*$")


class TokenError(Exception):
    """Base class for token verification failures."""


class TokenInvalid(TokenError):
    """Raised when a token's structure or signature is wrong."""


class TokenExpired(TokenError):
    """Raised when a token's signature is valid but its ``exp`` has passed."""


@dataclass(frozen=True)
class TokenPayload:
    """Decoded form-token payload.

    Attributes:
        request_id: The UUID of the :class:`CollectionRequest` this token
            authorizes the holder to fulfill.
        exp: Unix-second timestamp at which the token stops being valid.
    """

    request_id: UUID
    exp: int


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode ``data`` without padding (URL-safe)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Reverse :func:`_b64url_encode`. Raises on invalid input."""
    if not _BASE64URL_RE.match(data):
        raise binascii.Error(f"invalid base64url character in {data!r}")
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def sign_token(request_id: UUID, ttl_seconds: int, secret: str) -> str:
    """Mint a fresh, signed form token.

    Args:
        request_id: UUID of the collection request this token grants access to.
        ttl_seconds: Token lifetime. The :attr:`TokenPayload.exp` is set to
            ``int(time.time()) + ttl_seconds``.
        secret: HMAC key. In production this comes from Secret Manager via
            :class:`Settings.form_token_secret`.

    Returns:
        The compact token string (``payload_b64.signature_b64``).

    Raises:
        ValueError: If ``secret`` is empty or ``ttl_seconds`` is non-positive.
    """
    if not secret:
        raise ValueError("secret must be non-empty")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    payload = {"request_id": str(request_id), "exp": int(time.time()) + ttl_seconds}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def verify_token(token: str, secret: str) -> TokenPayload:
    """Verify ``token`` and return its decoded payload.

    Args:
        token: The compact token string to verify.
        secret: HMAC key — must match what :func:`sign_token` was called with.

    Returns:
        The decoded :class:`TokenPayload`.

    Raises:
        TokenInvalid: Token is malformed, the signature does not match, or
            the payload is not a JSON object with the expected fields.
        TokenExpired: Signature is valid but the token's ``exp`` has passed.
    """
    if not secret:
        raise ValueError("secret must be non-empty")

    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        signature = _b64url_decode(signature_b64)
    except (ValueError, binascii.Error) as exc:
        raise TokenInvalid("malformed token") from exc

    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise TokenInvalid("signature mismatch")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        request_id = UUID(payload["request_id"])
        exp = int(payload["exp"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise TokenInvalid("invalid payload") from exc

    if exp <= int(time.time()):
        raise TokenExpired("token has expired")

    return TokenPayload(request_id=request_id, exp=exp)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of ``token``.

    The collection-request record stores this digest, never the raw token,
    so a database leak alone cannot be replayed.

    Args:
        token: Raw token string.

    Returns:
        Hex SHA-256 digest (64 chars).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
