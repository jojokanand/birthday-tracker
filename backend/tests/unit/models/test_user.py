"""Unit tests for :class:`birthday_tracker.models.user.User`."""

from __future__ import annotations

import datetime as dt
import time

import pytest
from pydantic import ValidationError

from birthday_tracker.models import User


@pytest.mark.unit
def test_user_minimal() -> None:
    """A user can be built from just ``id`` + ``email``."""
    u = User(id="uid-123", email="alice@example.com")
    assert u.id == "uid-123"
    assert u.email == "alice@example.com"
    assert u.digest_owner_email is None
    assert u.digest_timezone == "UTC"


@pytest.mark.unit
def test_user_requires_id_and_email() -> None:
    with pytest.raises(ValidationError):
        User(email="alice@example.com")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        User(id="uid-123")  # type: ignore[call-arg]


@pytest.mark.unit
def test_user_invalid_email_rejected() -> None:
    with pytest.raises(ValidationError):
        User(id="uid-123", email="not-an-email")


@pytest.mark.unit
def test_effective_digest_email_falls_back_to_email() -> None:
    """``effective_digest_email`` is the explicit override or the sign-in email."""
    u = User(id="uid", email="me@example.com")
    assert u.effective_digest_email == "me@example.com"

    u2 = User(
        id="uid",
        email="me@example.com",
        digest_owner_email="shared@example.com",
    )
    assert u2.effective_digest_email == "shared@example.com"


@pytest.mark.unit
def test_touch_bumps_updated_at() -> None:
    u = User(id="uid", email="me@example.com")
    original = u.updated_at
    time.sleep(0.001)
    u.touch()
    assert u.updated_at > original


@pytest.mark.unit
def test_timestamps_are_utc() -> None:
    u = User(id="uid", email="me@example.com")
    assert u.created_at.tzinfo == dt.UTC
    assert u.updated_at.tzinfo == dt.UTC
