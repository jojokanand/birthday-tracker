"""Notifier protocols for outbound SMS and email.

Two narrow interfaces rather than one fat ``Notifier`` so each protocol exactly
matches what a single channel needs. Concrete adapters (Twilio for SMS, Gmail
API for email) live in :mod:`birthday_tracker.adapters` and are injected into
business-logic services that decide *which* channel to use for a given contact.
"""

from __future__ import annotations

from typing import Protocol


class NotificationError(Exception):
    """Raised by an adapter when the upstream provider rejects a send.

    The ``str(exc)`` payload is safe to log but may contain provider-specific
    text — never include it in user-facing responses.
    """


class SmsNotifier(Protocol):
    """Send a single SMS to one recipient."""

    async def send(self, to: str, body: str) -> str:
        """Deliver ``body`` to phone number ``to``.

        Args:
            to: E.164-formatted phone number (e.g. ``"+14155551234"``). The
                caller is responsible for normalization — implementations
                pass it through to the provider unchanged.
            body: Message text. Providers typically truncate at ~1600 chars
                and split into segments at 160 chars; the caller should keep
                messages short.

        Returns:
            The provider's message identifier, useful for log correlation.

        Raises:
            NotificationError: If the provider rejects the send.
        """
        ...  # pragma: no cover


class EmailNotifier(Protocol):
    """Send a single email to one recipient."""

    async def send(self, to: str, subject: str, html: str) -> str:
        """Deliver an HTML email.

        Args:
            to: Recipient email address. The caller is responsible for
                validating the format.
            subject: Subject line. Avoid newlines.
            html: HTML body. A plain-text fallback is generated automatically
                by the underlying client where possible.

        Returns:
            The provider's message identifier, useful for log correlation.

        Raises:
            NotificationError: If the provider rejects the send.
        """
        ...  # pragma: no cover
