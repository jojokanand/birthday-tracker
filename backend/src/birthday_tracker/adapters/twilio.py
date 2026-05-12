"""Twilio-backed SMS notifier.

The Twilio Python SDK is synchronous, so the actual ``messages.create`` call
is dispatched to a worker thread via :func:`asyncio.to_thread`. Keeping the
async surface lets callers ``await`` alongside Firestore I/O without blocking
the event loop.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from birthday_tracker.core.logging import get_logger
from birthday_tracker.services.notifiers import NotificationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from twilio.rest import Client as TwilioClient

logger = get_logger(__name__)


def build_twilio_client(account_sid: str, auth_token: str) -> TwilioClient:
    """Construct a Twilio :class:`Client`.

    Imported lazily so the module is importable in environments without the
    Twilio SDK installed (matches the pattern used by the Firestore adapter).

    Args:
        account_sid: Twilio Account SID. Empty string is allowed at config
            load time but rejected here to surface misconfiguration early.
        auth_token: Twilio Auth Token.

    Returns:
        A configured :class:`twilio.rest.Client`.

    Raises:
        ValueError: If ``account_sid`` or ``auth_token`` is empty.
    """
    if not account_sid or not auth_token:
        raise ValueError("Twilio account_sid and auth_token must both be non-empty")
    from twilio.rest import Client  # noqa: PLC0415

    return Client(account_sid, auth_token)


class TwilioNotifier:
    """A :class:`~birthday_tracker.services.SmsNotifier` backed by Twilio.

    Attributes:
        client: A :class:`twilio.rest.Client` (real or test). Injected so
            unit tests can pass a :class:`MagicMock`.
        from_number: E.164 number SMS will originate from. Must be a number
            owned by (or proxied through) the Twilio account.
    """

    def __init__(self, client: TwilioClient, from_number: str) -> None:
        """Build the notifier.

        Args:
            client: Pre-built Twilio client (use :func:`build_twilio_client`).
            from_number: E.164 sender number.

        Raises:
            ValueError: If ``from_number`` is empty.
        """
        if not from_number:
            raise ValueError("from_number must be non-empty")
        self.client = client
        self.from_number = from_number

    async def send(self, to: str, body: str) -> str:
        """Send an SMS to ``to`` via Twilio.

        Args:
            to: Recipient phone number in E.164 format.
            body: Message text.

        Returns:
            The Twilio message SID (e.g. ``"SM..."``).

        Raises:
            NotificationError: Wraps any exception raised by the Twilio SDK.
        """
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                to=to,
                from_=self.from_number,
                body=body,
            )
        except Exception as exc:  # noqa: BLE001 - SDK can raise many types
            logger.warning("twilio_send_failed", to=to, error=str(exc))
            raise NotificationError(f"Twilio send failed: {exc}") from exc

        sid: str = message.sid
        logger.info("twilio_sent", to=to, message_sid=sid)
        return sid
