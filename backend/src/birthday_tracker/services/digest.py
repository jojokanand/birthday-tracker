"""Daily birthday digest service.

Collects contacts whose birthday falls within a configurable look-ahead window
and emails a digest to the owner.  Idempotency is enforced per-process: if
:meth:`DigestService.send_digest` is called more than once on the same calendar
date, subsequent calls are no-ops.  For multi-instance Cloud Run deployments,
back the idempotency guard with a Firestore document as a follow-up.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from birthday_tracker.core.logging import get_logger
from birthday_tracker.services.notifiers import EmailNotifier
from birthday_tracker.services.repositories import ContactRepository

logger = get_logger(__name__)


@dataclass(frozen=True)
class UpcomingBirthday:
    """A contact paired with the number of days until their next birthday.

    Attributes:
        contact_id: UUID string of the contact.
        full_name: Contact's full legal name.
        preferred_name: Nickname / preferred name, if set.
        days_until: Days until the next birthday occurrence (0 = today).
    """

    contact_id: str
    full_name: str
    preferred_name: str | None
    days_until: int


def _days_until(month: int, day: int, today: dt.date) -> int:
    """Return the number of days from *today* until the next occurrence of month/day.

    Leap-day birthdays (02-29) map to 03-01 in non-leap years.

    Args:
        month: Birth month (1–12).
        day: Birth day (1–31).
        today: Reference date.

    Returns:
        Non-negative integer; 0 means the birthday is today.
    """

    def _bday_in(year: int) -> dt.date:
        try:
            return dt.date(year, month, day)
        except ValueError:
            return dt.date(year, 3, 1)  # 02-29 → 03-01

    candidate = _bday_in(today.year)
    if candidate < today:
        candidate = _bday_in(today.year + 1)
    return (candidate - today).days


def _render_html(items: list[UpcomingBirthday], today: dt.date) -> str:
    """Build a minimal HTML digest email body.

    Args:
        items: Upcoming birthdays, sorted by :attr:`UpcomingBirthday.days_until`.
        today: Reference date shown in the heading.

    Returns:
        An HTML string suitable for passing to an :class:`EmailNotifier`.
    """
    if not items:
        body = "<p>No birthdays in the upcoming window.</p>"
    else:
        rows = ""
        for b in items:
            name = b.preferred_name or b.full_name.split()[0]
            if b.days_until == 0:
                when = "<strong>Today 🎂</strong>"
            elif b.days_until == 1:
                when = "Tomorrow"
            else:
                when = f"in {b.days_until} days"
            rows += f"<tr><td>{b.full_name}</td><td>{name}</td><td>{when}</td></tr>\n"
        body = (
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<tr><th>Full name</th><th>Goes by</th><th>When</th></tr>"
            f"\n{rows}</table>"
        )

    return f"<html><body><h2>Birthday digest — {today.isoformat()}</h2>{body}</body></html>"


class DigestService:
    """Fetch upcoming birthdays and send a daily digest email to the owner.

    Attributes:
        _contacts: Contact repository used to load all contacts.
        _last_sent: Most recent date on which :meth:`send_digest` delivered
            an email.  ``None`` if no digest has been sent in this process
            lifetime.
    """

    def __init__(self, contacts: ContactRepository) -> None:
        """Initialise the service.

        Args:
            contacts: Repository from which all contacts are loaded.
        """
        self._contacts = contacts
        self._last_sent: dt.date | None = None

    async def get_upcoming(
        self,
        days: int = 14,
        today: dt.date | None = None,
    ) -> list[UpcomingBirthday]:
        """Return contacts with a birthday in the next *days* calendar days.

        Args:
            days: Inclusive look-ahead window (0 = today only).
            today: Override the current date (useful in tests).

        Returns:
            List of :class:`UpcomingBirthday` sorted by
            :attr:`~UpcomingBirthday.days_until` ascending.
        """
        reference = today or dt.date.today()
        contacts = await self._contacts.list_all()
        results: list[UpcomingBirthday] = []
        for contact in contacts:
            if contact.birthday is None:
                continue
            d = _days_until(contact.birthday.month, contact.birthday.day, reference)
            if d <= days:
                results.append(
                    UpcomingBirthday(
                        contact_id=str(contact.id),
                        full_name=contact.full_name,
                        preferred_name=contact.preferred_name,
                        days_until=d,
                    )
                )
        results.sort(key=lambda b: b.days_until)
        return results

    async def send_digest(
        self,
        notifier: EmailNotifier,
        owner_email: str,
        days: int = 14,
        today: dt.date | None = None,
    ) -> bool:
        """Send the digest email, skipping if one was already sent today.

        Args:
            notifier: :class:`~birthday_tracker.services.notifiers.EmailNotifier`
                implementation used to deliver the email.
            owner_email: Recipient address (the birthday tracker owner).
            days: Look-ahead window passed to :meth:`get_upcoming`.
            today: Override the current date (useful in tests).

        Returns:
            ``True`` if the email was delivered, ``False`` if it was skipped
            because the digest was already sent today.
        """
        reference = today or dt.date.today()

        if self._last_sent == reference:
            logger.info(
                "digest_skipped",
                reason="already_sent_today",
                date=reference.isoformat(),
            )
            return False

        upcoming = await self.get_upcoming(days=days, today=reference)
        subject = f"Birthday digest — {reference.isoformat()} ({len(upcoming)} upcoming)"
        html = _render_html(upcoming, reference)
        await notifier.send(to=owner_email, subject=subject, html=html)
        self._last_sent = reference
        logger.info(
            "digest_sent",
            to=owner_email,
            count=len(upcoming),
            date=reference.isoformat(),
        )
        return True
