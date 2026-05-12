"""Unit tests for TwilioNotifier (SMS adapter)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from birthday_tracker.adapters import TwilioNotifier, build_twilio_client
from birthday_tracker.services import NotificationError


@pytest.fixture
def fake_client() -> MagicMock:
    """Build a Twilio client mock whose ``messages.create`` returns a SID."""
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid="SM0123456789abcdef")
    return client


@pytest.mark.unit
async def test_send_invokes_twilio_with_correct_args(fake_client: MagicMock) -> None:
    notifier = TwilioNotifier(client=fake_client, from_number="+14155551111")
    sid = await notifier.send(to="+14155552222", body="Hello!")

    assert sid == "SM0123456789abcdef"
    fake_client.messages.create.assert_called_once_with(
        to="+14155552222",
        from_="+14155551111",
        body="Hello!",
    )


@pytest.mark.unit
async def test_send_wraps_sdk_errors_as_notification_error(fake_client: MagicMock) -> None:
    fake_client.messages.create.side_effect = RuntimeError("network down")
    notifier = TwilioNotifier(client=fake_client, from_number="+14155551111")

    with pytest.raises(NotificationError, match="Twilio send failed: network down"):
        await notifier.send(to="+14155552222", body="Hi")


@pytest.mark.unit
def test_constructor_rejects_blank_from_number(fake_client: MagicMock) -> None:
    with pytest.raises(ValueError, match="from_number must be non-empty"):
        TwilioNotifier(client=fake_client, from_number="")


@pytest.mark.unit
def test_build_twilio_client_rejects_blank_creds() -> None:
    with pytest.raises(ValueError, match="must both be non-empty"):
        build_twilio_client(account_sid="", auth_token="x")
    with pytest.raises(ValueError, match="must both be non-empty"):
        build_twilio_client(account_sid="x", auth_token="")


@pytest.mark.unit
def test_build_twilio_client_constructs_real_client() -> None:
    """Lazy import + constructor wiring — patches twilio.rest.Client to verify."""
    fake_class = MagicMock(return_value=MagicMock(name="client"))
    with patch("twilio.rest.Client", fake_class):
        client = build_twilio_client(account_sid="ACtest", auth_token="tok")
    fake_class.assert_called_once_with("ACtest", "tok")
    assert client is fake_class.return_value
