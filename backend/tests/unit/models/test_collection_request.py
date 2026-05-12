"""Unit tests for the CollectionRequest model."""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest
from pydantic import ValidationError

from birthday_tracker.models import Channel, CollectionRequest

VALID_HASH = "a" * 64
OWNER = "test-owner"


@pytest.mark.unit
def test_create_with_required_fields() -> None:
    req = CollectionRequest(
        owner_id=OWNER,
        contact_id=uuid4(),
        channel=Channel.email,
        destination="ada@example.com",
        token_hash=VALID_HASH,
    )
    assert req.is_pending is True
    assert req.fulfilled_at is None
    assert req.expires_at > req.created_at
    assert req.owner_id == OWNER


@pytest.mark.unit
def test_token_hash_must_be_64_chars() -> None:
    with pytest.raises(ValidationError):
        CollectionRequest(
            owner_id=OWNER,
            contact_id=uuid4(),
            channel=Channel.sms,
            destination="+14155551234",
            token_hash="too-short",
        )


@pytest.mark.unit
def test_expires_must_be_after_created() -> None:
    now = dt.datetime.now(dt.UTC)
    with pytest.raises(ValidationError, match="expires_at must be strictly after"):
        CollectionRequest(
            owner_id=OWNER,
            contact_id=uuid4(),
            channel=Channel.email,
            destination="x@y.com",
            token_hash=VALID_HASH,
            created_at=now,
            expires_at=now,
        )


@pytest.mark.unit
def test_fulfilled_request_is_not_pending() -> None:
    req = CollectionRequest(
        owner_id=OWNER,
        contact_id=uuid4(),
        channel=Channel.email,
        destination="x@y.com",
        token_hash=VALID_HASH,
        fulfilled_at=dt.datetime.now(dt.UTC),
    )
    assert req.is_pending is False


@pytest.mark.unit
def test_expired_pending_request_is_not_pending() -> None:
    past = dt.datetime.now(dt.UTC) - dt.timedelta(days=10)
    req = CollectionRequest(
        owner_id=OWNER,
        contact_id=uuid4(),
        channel=Channel.email,
        destination="x@y.com",
        token_hash=VALID_HASH,
        created_at=past - dt.timedelta(days=1),
        expires_at=past,
    )
    assert req.is_pending is False


@pytest.mark.unit
def test_owner_id_is_required() -> None:
    """``owner_id`` is mandatory — the API layer must set it from auth."""
    with pytest.raises(ValidationError):
        CollectionRequest(  # type: ignore[call-arg]
            contact_id=uuid4(),
            channel=Channel.email,
            destination="x@y.com",
            token_hash=VALID_HASH,
        )
