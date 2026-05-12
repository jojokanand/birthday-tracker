"""Integration test for TwilioNotifier against Twilio test credentials.

Skipped unless ``TWILIO_TEST_ACCOUNT_SID`` and ``TWILIO_TEST_AUTH_TOKEN`` are
set. Twilio's test credentials accept "magic" phone numbers that always
succeed (``+15005550006``) — we use one as both the from and to number so the
API call exercises the real wire format without sending real SMS.
"""

from __future__ import annotations

import os

import pytest

from birthday_tracker.adapters import TwilioNotifier, build_twilio_client

TEST_SID_ENV = "TWILIO_TEST_ACCOUNT_SID"
TEST_TOKEN_ENV = "TWILIO_TEST_AUTH_TOKEN"
MAGIC_NUMBER = "+15005550006"


def _twilio_test_creds_present() -> bool:
    """``True`` iff both Twilio test-credential env vars are populated."""
    return bool(os.environ.get(TEST_SID_ENV)) and bool(os.environ.get(TEST_TOKEN_ENV))


@pytest.mark.integration
async def test_send_against_twilio_test_credentials() -> None:
    """End-to-end send via the Twilio API using test credentials + a magic number."""
    if not _twilio_test_creds_present():
        pytest.skip(f"Set {TEST_SID_ENV} and {TEST_TOKEN_ENV} to run this test")

    client = build_twilio_client(
        account_sid=os.environ[TEST_SID_ENV],
        auth_token=os.environ[TEST_TOKEN_ENV],
    )
    notifier = TwilioNotifier(client=client, from_number=MAGIC_NUMBER)
    sid = await notifier.send(to=MAGIC_NUMBER, body="integration test")

    assert sid.startswith("SM")
