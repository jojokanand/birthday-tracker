"""Unit tests for :mod:`birthday_tracker.services.digest`.

Uses an :class:`~birthday_tracker.adapters.InMemoryContactRepository` and a
stub email notifier so no external services are touched.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock

import pytest

from birthday_tracker.adapters import InMemoryContactRepository
from birthday_tracker.models import Contact
from birthday_tracker.models.birthday import Birthday
from birthday_tracker.services.digest import DigestService, _days_until, _render_html

# ---------------------------------------------------------------------------
# _days_until unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDaysUntil:
    """Tests for the :func:`~birthday_tracker.services.digest._days_until` helper."""

    def test_today(self) -> None:
        """Birthday month/day matching today returns 0."""
        today = dt.date(2024, 6, 15)
        assert _days_until(6, 15, today) == 0

    def test_tomorrow(self) -> None:
        """Birthday tomorrow returns 1."""
        today = dt.date(2024, 6, 15)
        assert _days_until(6, 16, today) == 1

    def test_wraps_to_next_year(self) -> None:
        """A birthday that already passed this year wraps to next year."""
        today = dt.date(2024, 6, 15)
        # Birthday on June 10 — already passed this year, next is 2025-06-10.
        expected = (dt.date(2025, 6, 10) - today).days  # 360
        assert _days_until(6, 10, today) == expected

    def test_leap_day_in_non_leap_year(self) -> None:
        """Feb 29 maps to Mar 1 in non-leap years."""
        today = dt.date(2025, 2, 28)
        # 2025 is not a leap year; 02-29 → 03-01
        assert _days_until(2, 29, today) == 1

    def test_leap_day_in_leap_year(self) -> None:
        """Feb 29 is honoured directly in a leap year."""
        today = dt.date(2024, 2, 28)
        assert _days_until(2, 29, today) == 1

    def test_year_boundary(self) -> None:
        """Birthday on Jan 1 from Dec 31 returns 1."""
        today = dt.date(2024, 12, 31)
        assert _days_until(1, 1, today) == 1


# ---------------------------------------------------------------------------
# _render_html
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderHtml:
    """Tests for :func:`~birthday_tracker.services.digest._render_html`."""

    def test_empty_list(self) -> None:
        """An empty upcoming list produces a 'no birthdays' message."""
        html = _render_html([], dt.date(2024, 6, 15))
        assert "No birthdays" in html

    def test_contains_names(self) -> None:
        """Each contact's full name appears in the rendered HTML."""
        from birthday_tracker.services.digest import UpcomingBirthday

        items = [
            UpcomingBirthday(
                contact_id="a",
                full_name="Ada Lovelace",
                preferred_name="Ada",
                days_until=0,
            ),
            UpcomingBirthday(
                contact_id="b",
                full_name="Charles Babbage",
                preferred_name=None,
                days_until=5,
            ),
        ]
        html = _render_html(items, dt.date(2024, 6, 15))
        assert "Ada Lovelace" in html
        assert "Charles Babbage" in html
        assert "Today" in html
        assert "in 5 days" in html


# ---------------------------------------------------------------------------
# DigestService.get_upcoming
# ---------------------------------------------------------------------------


async def _make_service(contacts: list[Contact]) -> DigestService:
    repo = InMemoryContactRepository()
    for c in contacts:
        await repo.save(c)
    return DigestService(contacts=repo)


@pytest.mark.unit
class TestGetUpcoming:
    """Tests for :meth:`DigestService.get_upcoming`."""

    @pytest.mark.asyncio
    async def test_filters_within_window(self) -> None:
        """Only contacts with birthday within *days* are returned."""
        today = dt.date(2024, 6, 15)
        contacts = [
            Contact(
                full_name="Soon",
                email="soon@example.com",
                birthday=Birthday(month=6, day=20),  # 5 days
            ),
            Contact(
                full_name="Later",
                email="later@example.com",
                birthday=Birthday(month=7, day=15),  # 30 days
            ),
        ]
        service = await _make_service(contacts)
        results = await service.get_upcoming(days=14, today=today)
        assert len(results) == 1
        assert results[0].full_name == "Soon"
        assert results[0].days_until == 5

    @pytest.mark.asyncio
    async def test_excludes_contacts_without_birthday(self) -> None:
        """Contacts with no birthday are excluded regardless of window."""
        contacts = [Contact(full_name="No Birthday", email="nb@example.com")]
        service = await _make_service(contacts)
        results = await service.get_upcoming(days=365, today=dt.date(2024, 6, 15))
        assert results == []

    @pytest.mark.asyncio
    async def test_sorted_by_days_until(self) -> None:
        """Results are sorted ascending by days_until."""
        today = dt.date(2024, 6, 15)
        contacts = [
            Contact(
                full_name="B",
                email="b@example.com",
                birthday=Birthday(month=6, day=17),  # 2 days
            ),
            Contact(
                full_name="A",
                email="a@example.com",
                birthday=Birthday(month=6, day=16),  # 1 day
            ),
        ]
        service = await _make_service(contacts)
        results = await service.get_upcoming(days=14, today=today)
        assert [r.full_name for r in results] == ["A", "B"]

    @pytest.mark.asyncio
    async def test_today_included(self) -> None:
        """A birthday today (days_until=0) is included in the window."""
        today = dt.date(2024, 6, 15)
        contacts = [
            Contact(
                full_name="Today",
                email="today@example.com",
                birthday=Birthday(month=6, day=15),
            ),
        ]
        service = await _make_service(contacts)
        results = await service.get_upcoming(days=0, today=today)
        assert len(results) == 1
        assert results[0].days_until == 0


# ---------------------------------------------------------------------------
# DigestService.send_digest
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendDigest:
    """Tests for :meth:`DigestService.send_digest` including idempotency."""

    @pytest.mark.asyncio
    async def test_sends_email(self) -> None:
        """send_digest calls the notifier and returns True on the first call."""
        today = dt.date(2024, 6, 15)
        contacts = [
            Contact(
                full_name="Ada Lovelace",
                email="ada@example.com",
                birthday=Birthday(month=6, day=20),
            )
        ]
        service = await _make_service(contacts)
        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value="msg-id-1")

        sent = await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=today
        )

        assert sent is True
        notifier.send.assert_awaited_once()
        call_kwargs = notifier.send.call_args.kwargs
        assert call_kwargs["to"] == "owner@example.com"
        assert "digest" in call_kwargs["subject"].lower()

    @pytest.mark.asyncio
    async def test_idempotent_second_call(self) -> None:
        """A second call on the same date returns False without sending again."""
        today = dt.date(2024, 6, 15)
        service = await _make_service([])
        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value="msg-id-1")

        first = await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=today
        )
        second = await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=today
        )

        assert first is True
        assert second is False
        notifier.send.assert_awaited_once()  # only once, not twice

    @pytest.mark.asyncio
    async def test_different_day_sends_again(self) -> None:
        """A call on a different date sends a fresh digest."""
        service = await _make_service([])
        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value="msg-id")

        await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=dt.date(2024, 6, 15)
        )
        await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=dt.date(2024, 6, 16)
        )

        assert notifier.send.await_count == 2

    @pytest.mark.asyncio
    async def test_sends_even_with_empty_list(self) -> None:
        """A digest with no upcoming birthdays is still delivered (zero-count digest)."""
        today = dt.date(2024, 6, 15)
        service = await _make_service([])
        notifier = AsyncMock()
        notifier.send = AsyncMock(return_value="msg-id")

        sent = await service.send_digest(
            notifier=notifier, owner_email="owner@example.com", today=today
        )

        assert sent is True
        notifier.send.assert_awaited_once()
