"""Unit tests for the Birthday model."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from birthday_tracker.models import Birthday


@pytest.mark.unit
def test_simple_birthday() -> None:
    bd = Birthday(month=5, day=11, year=1990)
    assert (bd.month, bd.day, bd.year) == (5, 11, 1990)


@pytest.mark.unit
def test_birthday_without_year_is_allowed() -> None:
    bd = Birthday(month=5, day=11)
    assert bd.year is None


@pytest.mark.unit
def test_feb_29_without_year_accepted() -> None:
    """02-29 is valid when the year is unknown — we probe with a leap year."""
    bd = Birthday(month=2, day=29)
    assert bd.month == 2 and bd.day == 29


@pytest.mark.unit
def test_feb_29_in_non_leap_year_rejected() -> None:
    with pytest.raises(ValidationError):
        Birthday(month=2, day=29, year=2023)


@pytest.mark.unit
def test_feb_30_always_rejected() -> None:
    with pytest.raises(ValidationError):
        Birthday(month=2, day=30)


@pytest.mark.unit
def test_month_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Birthday(month=13, day=1)


@pytest.mark.unit
def test_day_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Birthday(month=1, day=0)


@pytest.mark.unit
def test_year_in_future_rejected() -> None:
    next_year = dt.date.today().year + 1
    with pytest.raises(ValidationError):
        Birthday(month=1, day=1, year=next_year)


@pytest.mark.unit
def test_year_too_old_rejected() -> None:
    with pytest.raises(ValidationError):
        Birthday(month=1, day=1, year=1800)
