"""Unit tests for the Contact aggregate model."""

from __future__ import annotations

import datetime as dt
import time

import pytest
from pydantic import ValidationError

from birthday_tracker.models import Address, Birthday, Contact

OWNER = "test-owner"


@pytest.mark.unit
def test_contact_with_email_only() -> None:
    c = Contact(owner_id=OWNER, full_name="Ada Lovelace", email="ada@example.com")
    assert c.email == "ada@example.com"
    assert c.phone is None
    assert c.id is not None
    assert c.owner_id == OWNER


@pytest.mark.unit
def test_contact_with_phone_only_normalizes_to_e164() -> None:
    c = Contact(owner_id=OWNER, full_name="Ada Lovelace", phone="(415) 555-1234")
    assert c.phone == "+14155551234"


@pytest.mark.unit
def test_contact_phone_already_e164() -> None:
    c = Contact(owner_id=OWNER, full_name="Ada", phone="+442071838750")
    assert c.phone == "+442071838750"


@pytest.mark.unit
def test_contact_invalid_phone_rejected() -> None:
    with pytest.raises(ValidationError):
        Contact(owner_id=OWNER, full_name="Ada", phone="not-a-phone")


@pytest.mark.unit
def test_contact_phone_parses_but_invalid_number_rejected() -> None:
    """Covers the `not is_valid_number` branch (parses but fails validity check)."""
    with pytest.raises(ValidationError, match="invalid phone number"):
        Contact(owner_id=OWNER, full_name="Ada", phone="+1 555 0100")


@pytest.mark.unit
def test_contact_explicit_none_phone() -> None:
    """Explicit ``phone=None`` triggers the validator's early-return branch."""
    c = Contact(owner_id=OWNER, full_name="Ada", email="ada@example.com", phone=None)
    assert c.phone is None


@pytest.mark.unit
def test_contact_requires_email_or_phone() -> None:
    with pytest.raises(ValidationError, match="at least one of email or phone"):
        Contact(owner_id=OWNER, full_name="Ada")


@pytest.mark.unit
def test_contact_invalid_email_rejected() -> None:
    with pytest.raises(ValidationError):
        Contact(owner_id=OWNER, full_name="Ada", email="not-an-email")


@pytest.mark.unit
def test_contact_requires_owner_id() -> None:
    """``owner_id`` is required — the API layer must set it from auth."""
    with pytest.raises(ValidationError):
        Contact(full_name="Ada", email="ada@example.com")  # type: ignore[call-arg]


@pytest.mark.unit
def test_contact_with_full_payload() -> None:
    c = Contact(
        owner_id=OWNER,
        full_name="Ada Lovelace",
        preferred_name="Ada",
        email="ada@example.com",
        phone="+14155551234",
        address=Address(street1="1 Main", city="London", country="GB"),
        birthday=Birthday(month=12, day=10, year=1990),
    )
    assert c.preferred_name == "Ada"
    assert c.address is not None and c.address.country == "GB"
    assert c.birthday is not None and c.birthday.year == 1990


@pytest.mark.unit
def test_touch_updates_updated_at() -> None:
    c = Contact(owner_id=OWNER, full_name="Ada", email="ada@example.com")
    original = c.updated_at
    time.sleep(0.001)
    c.touch()
    assert c.updated_at > original


@pytest.mark.unit
def test_created_at_is_utc() -> None:
    c = Contact(owner_id=OWNER, full_name="Ada", email="ada@example.com")
    assert c.created_at.tzinfo == dt.UTC
