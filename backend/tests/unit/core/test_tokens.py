"""Unit tests for HMAC form-token primitives."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from birthday_tracker.core.tokens import (
    TokenExpired,
    TokenInvalid,
    hash_token,
    sign_token,
    verify_token,
)

SECRET = "unit-test-secret"


@pytest.mark.unit
def test_round_trip_returns_payload() -> None:
    request_id = uuid4()
    token = sign_token(request_id=request_id, ttl_seconds=60, secret=SECRET)
    payload = verify_token(token, SECRET)
    assert payload.request_id == request_id
    assert payload.exp > int(time.time())


@pytest.mark.unit
def test_sign_rejects_blank_secret() -> None:
    with pytest.raises(ValueError, match="secret must be non-empty"):
        sign_token(request_id=uuid4(), ttl_seconds=60, secret="")


@pytest.mark.unit
def test_sign_rejects_non_positive_ttl() -> None:
    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        sign_token(request_id=uuid4(), ttl_seconds=0, secret=SECRET)


@pytest.mark.unit
def test_verify_rejects_blank_secret() -> None:
    token = sign_token(request_id=uuid4(), ttl_seconds=60, secret=SECRET)
    with pytest.raises(ValueError, match="secret must be non-empty"):
        verify_token(token, "")


@pytest.mark.unit
def test_verify_rejects_malformed_token() -> None:
    with pytest.raises(TokenInvalid, match="malformed"):
        verify_token("nodot", SECRET)


@pytest.mark.unit
def test_verify_rejects_undecodable_token() -> None:
    with pytest.raises(TokenInvalid, match="malformed"):
        verify_token("!!!.!!!", SECRET)


@pytest.mark.unit
def test_verify_rejects_signature_mismatch() -> None:
    token = sign_token(request_id=uuid4(), ttl_seconds=60, secret=SECRET)
    payload_b64, _ = token.split(".")
    tampered = f"{payload_b64}.AAAA"
    with pytest.raises(TokenInvalid, match="signature mismatch"):
        verify_token(tampered, SECRET)


@pytest.mark.unit
def test_verify_rejects_payload_with_missing_fields() -> None:
    """A signature-valid payload that's missing ``exp`` is invalid."""
    import base64
    import hashlib
    import hmac
    import json

    payload = json.dumps({"request_id": str(uuid4())}).encode("utf-8")
    sig = hmac.new(SECRET.encode(), payload, hashlib.sha256).digest()

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    token = f"{b64(payload)}.{b64(sig)}"
    with pytest.raises(TokenInvalid, match="invalid payload"):
        verify_token(token, SECRET)


@pytest.mark.unit
def test_verify_raises_token_expired_after_exp() -> None:
    token = sign_token(request_id=uuid4(), ttl_seconds=1, secret=SECRET)
    time.sleep(1.1)
    with pytest.raises(TokenExpired):
        verify_token(token, SECRET)


@pytest.mark.unit
def test_hash_token_is_deterministic_and_64_hex() -> None:
    digest_a = hash_token("some-token")
    digest_b = hash_token("some-token")
    assert digest_a == digest_b
    assert len(digest_a) == 64
    int(digest_a, 16)  # raises if not hex
