"""Unit tests for the Address model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from birthday_tracker.models import Address


@pytest.mark.unit
def test_minimum_required_fields() -> None:
    addr = Address(street1="1 Main", city="Anytown")
    assert addr.country == "US"
    assert addr.street2 is None
    assert addr.region is None
    assert addr.postal_code is None


@pytest.mark.unit
def test_country_is_uppercased() -> None:
    addr = Address(street1="1 Main", city="Anytown", country="gb")
    assert addr.country == "GB"


@pytest.mark.unit
def test_blank_street1_rejected() -> None:
    with pytest.raises(ValidationError):
        Address(street1="", city="Anytown")


@pytest.mark.unit
def test_blank_city_rejected() -> None:
    with pytest.raises(ValidationError):
        Address(street1="1 Main", city="")


@pytest.mark.unit
def test_country_must_be_two_chars() -> None:
    with pytest.raises(ValidationError):
        Address(street1="1 Main", city="Anytown", country="USA")
