"""Integration test for GmailNotifier against a real Gmail OAuth grant.

Skipped unless all three env vars are set:

- ``GMAIL_OAUTH_CLIENT_SECRETS_PATH``
- ``GMAIL_OAUTH_TOKEN_PATH``        (must already exist; bootstrap with the
  one-time CLI flow described in ``backend/README.md``)
- ``GMAIL_INTEGRATION_TO``          recipient address, typically your own

Sends a single labelled message; check your inbox afterwards.
"""

from __future__ import annotations

import os

import pytest

from birthday_tracker.adapters import (
    GmailNotifier,
    build_gmail_service,
    load_gmail_credentials,
)

CLIENT_SECRETS_ENV = "GMAIL_OAUTH_CLIENT_SECRETS_PATH"
TOKEN_PATH_ENV = "GMAIL_OAUTH_TOKEN_PATH"
RECIPIENT_ENV = "GMAIL_INTEGRATION_TO"
FROM_ADDRESS_ENV = "GMAIL_FROM_ADDRESS"


def _gmail_creds_present() -> bool:
    """All three creds env vars are set and the token file exists on disk."""
    secrets = os.environ.get(CLIENT_SECRETS_ENV, "")
    token = os.environ.get(TOKEN_PATH_ENV, "")
    recipient = os.environ.get(RECIPIENT_ENV, "")
    return bool(secrets) and bool(token) and os.path.exists(token) and bool(recipient)


@pytest.mark.integration
async def test_send_against_real_gmail() -> None:
    """End-to-end send via the Gmail API using the cached OAuth refresh token."""
    if not _gmail_creds_present():
        pytest.skip(
            f"Set {CLIENT_SECRETS_ENV}, {TOKEN_PATH_ENV} (existing), and "
            f"{RECIPIENT_ENV} to run this test."
        )

    creds = load_gmail_credentials(
        client_secrets_path=os.environ[CLIENT_SECRETS_ENV],
        token_path=os.environ[TOKEN_PATH_ENV],
    )
    service = build_gmail_service(creds)
    notifier = GmailNotifier(
        service=service,
        from_address=os.environ.get(FROM_ADDRESS_ENV, "me"),
    )

    msg_id = await notifier.send(
        to=os.environ[RECIPIENT_ENV],
        subject="[birthday-tracker] integration test",
        html="<p>If you received this, the Gmail adapter works end-to-end.</p>",
    )
    assert msg_id
