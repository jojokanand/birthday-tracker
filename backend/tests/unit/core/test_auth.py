"""Unit tests for :mod:`birthday_tracker.core.auth`.

The Firebase verification path is mocked so tests stay offline.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from birthday_tracker.core.auth import (
    Identity,
    dev_identity,
    verify_firebase_id_token,
)


@pytest.mark.unit
def test_dev_identity_is_stable() -> None:
    """``dev_identity()`` returns a fixed sentinel — used for tests/dev."""
    one = dev_identity()
    two = dev_identity()
    assert one == two
    assert isinstance(one, Identity)
    assert one.user_id and one.email


@pytest.mark.unit
def test_verify_returns_identity_for_valid_token() -> None:
    """A valid Firebase token yields an :class:`Identity` with uid + email."""
    decoded = {"uid": "abc123", "email": "alice@example.com"}
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", return_value=decoded),
    ):
        ident = verify_firebase_id_token("any-jwt")

    assert ident.user_id == "abc123"
    assert ident.email == "alice@example.com"


@pytest.mark.unit
def test_verify_raises_when_sdk_rejects() -> None:
    """Any exception from the Firebase SDK propagates as ``ValueError``."""

    def _boom(*_: object, **__: object) -> None:
        raise RuntimeError("expired")

    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", side_effect=_boom),
        pytest.raises(ValueError, match="invalid Firebase ID token"),
    ):
        verify_firebase_id_token("bad-jwt")


@pytest.mark.unit
def test_verify_rejects_token_without_uid() -> None:
    """A decoded token missing ``uid`` is rejected."""
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"email": "x@y.com"},
        ),
        pytest.raises(ValueError, match="uid"),
    ):
        verify_firebase_id_token("token")


@pytest.mark.unit
def test_verify_rejects_token_without_email() -> None:
    """A decoded token missing ``email`` is rejected."""
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch(
            "firebase_admin.auth.verify_id_token",
            return_value={"uid": "abc"},
        ),
        pytest.raises(ValueError, match="email"),
    ):
        verify_firebase_id_token("token")


@pytest.mark.unit
def test_verify_carries_display_name_when_present() -> None:
    """The Firebase ``name`` claim flows onto ``Identity.display_name``."""
    decoded = {
        "uid": "abc",
        "email": "alice@example.com",
        "name": "Alice Lovelace",
    }
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", return_value=decoded),
    ):
        ident = verify_firebase_id_token("token")

    assert ident.display_name == "Alice Lovelace"


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "", "   ", 12345])
def test_verify_treats_blank_or_non_string_name_as_absent(value: object) -> None:
    """Empty / whitespace / non-string names collapse to ``None``."""
    decoded = {"uid": "abc", "email": "alice@example.com", "name": value}
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", return_value=decoded),
    ):
        ident = verify_firebase_id_token("token")

    assert ident.display_name is None


@pytest.mark.unit
def test_dev_identity_has_display_name() -> None:
    """Dev mode supplies a placeholder name so local emails read naturally."""
    assert dev_identity().display_name == "Dev User"


@pytest.mark.unit
def test_verify_carries_phone_number_when_present() -> None:
    """The Firebase ``phone_number`` claim flows onto ``Identity.phone_number``."""
    decoded = {
        "uid": "abc",
        "email": "alice@example.com",
        "phone_number": "+14155551234",
    }
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", return_value=decoded),
    ):
        ident = verify_firebase_id_token("token")

    assert ident.phone_number == "+14155551234"


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "", "   ", 5551234])
def test_verify_treats_blank_or_non_string_phone_as_absent(value: object) -> None:
    """Empty / non-string phone_number collapses to ``None``."""
    decoded = {
        "uid": "abc",
        "email": "alice@example.com",
        "phone_number": value,
    }
    with (
        patch("birthday_tracker.core.auth._ensure_firebase_initialized"),
        patch("firebase_admin.auth.verify_id_token", return_value=decoded),
    ):
        ident = verify_firebase_id_token("token")

    assert ident.phone_number is None
