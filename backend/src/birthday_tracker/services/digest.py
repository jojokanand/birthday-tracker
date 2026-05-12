"""Daily birthday digest service.

Collects each user's contacts whose birthday falls within a configurable
look-ahead window and emails a digest to that user. Idempotency is
enforced per-process and per-owner: if :meth:`DigestService.send_digest`
is called more than once for the same ``(owner_id, date)`` pair, the
second call is a no-op. For multi-instance Cloud Run deployments, back
the idempotency guard with a Firestore document as a follow-up.
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
    """Build and send the daily birthday digest for a single user.

    Each call is scoped to one ``owner_id`` so the orchestration layer
    (typically the ``/internal/digest/send`` endpoint) decides who to
    iterate. Idempotency is tracked per-owner so two users on the same
    process don't accidentally cancel each other out.

    Attributes:
        _contacts: Contact repository used to load each owner's contacts.
        _last_sent: Per-owner record of the most recent date a digest was
            delivered. Used to short-circuit duplicate calls within the
            same process lifetime.
    """

    def __init__(self, contacts: ContactRepository) -> None:
        """Initialise the service.

        Args:
            contacts: Repository from which contacts are loaded (scoped per
                owner on each call).
        """
        self._contacts = contacts
        self._last_sent: dict[str, dt.date] = {}

    async def get_upcoming(
        self,
        owner_id: str,
        days: int = 14,
        today: dt.date | None = None,
    ) -> list[UpcomingBirthday]:
        """Return ``owner_id``'s contacts with a birthday in the next *days* days.

        Args:
            owner_id: Firebase ``uid`` whose contacts to load.
            days: Inclusive look-ahead window (0 = today only).
            today: Override the current date (useful in tests).

        Returns:
            List of :class:`UpcomingBirthday` sorted by
            :attr:`~UpcomingBirthday.days_until` ascending.
        """
        reference = today or dt.date.today()
        contacts = await self._contacts.list_for_owner(owner_id)
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
        owner_id: str,
        owner_email: str,
        days: int = 14,
        today: dt.date | None = None,
    ) -> bool:
        """Send ``owner_id``'s daily digest, skipping duplicates.

        Args:
            notifier: :class:`~birthday_tracker.services.notifiers.EmailNotifier`
                implementation used to deliver the email.
            owner_id: Firebase ``uid`` whose contacts to summarise.
            owner_email: Recipient address (the user's
                :attr:`~birthday_tracker.models.User.effective_digest_email`).
            days: Look-ahead window passed to :meth:`get_upcoming`.
            today: Override the current date (useful in tests).

        Returns:
            ``True`` if the email was delivered, ``False`` if it was skipped
            because the digest was already sent for this ``(owner_id, date)``.
        """
        reference = today or dt.date.today()

        if self._last_sent.get(owner_id) == reference:
            logger.info(
                "digest_skipped",
                reason="already_sent_today",
                owner_id=owner_id,
                date=reference.isoformat(),
            )
            return False

        upcoming = await self.get_upcoming(owner_id=owner_id, days=days, today=reference)
        subject = f"Birthday digest — {reference.isoformat()} ({len(upcoming)} upcoming)"
        html = _render_html(upcoming, reference)
        await notifier.send(to=owner_email, subject=subject, html=html)
        self._last_sent[owner_id] = reference
        logger.info(
            "digest_sent",
            owner_id=owner_id,
            to=owner_email,
            count=len(upcoming),
            date=reference.isoformat(),
        )
        return True
