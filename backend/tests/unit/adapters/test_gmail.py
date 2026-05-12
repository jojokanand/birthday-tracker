"""Unit tests for GmailNotifier (email adapter)."""

from __future__ import annotations

import base64
import os
from email import message_from_bytes, policy
from unittest.mock import MagicMock, mock_open, patch

import pytest

from birthday_tracker.adapters import GmailNotifier, build_gmail_service, load_gmail_credentials
from birthday_tracker.adapters.gmail import _encode_email
from birthday_tracker.services import NotificationError


@pytest.fixture
def fake_service() -> MagicMock:
    """Build a Gmail service mock whose send chain returns a message id."""
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "msg-123",
    }
    return service


@pytest.mark.unit
async def test_send_invokes_gmail_with_encoded_payload(fake_service: MagicMock) -> None:
    notifier = GmailNotifier(service=fake_service, from_address="me@example.com")

    msg_id = await notifier.send(
        to="recipient@example.com",
        subject="Hi",
        html="<p>hello</p>",
    )

    assert msg_id == "msg-123"
    send_call = fake_service.users.return_value.messages.return_value.send
    send_call.assert_called_once()
    kwargs = send_call.call_args.kwargs
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]


@pytest.mark.unit
async def test_send_wraps_sdk_errors(fake_service: MagicMock) -> None:
    chain = fake_service.users.return_value.messages.return_value.send.return_value
    chain.execute.side_effect = RuntimeError("quota exceeded")

    notifier = GmailNotifier(service=fake_service, from_address="me@example.com")
    with pytest.raises(NotificationError, match="Gmail send failed: quota exceeded"):
        await notifier.send(to="x@y.com", subject="s", html="<p/>")


@pytest.mark.unit
def test_constructor_rejects_blank_from_address(fake_service: MagicMock) -> None:
    with pytest.raises(ValueError, match="from_address must be non-empty"):
        GmailNotifier(service=fake_service, from_address="")


@pytest.mark.unit
def test_encode_email_round_trips() -> None:
    """The encoded payload decodes back into the original headers + HTML body."""
    payload = _encode_email(
        from_addr="me@example.com",
        to="you@example.com",
        subject="Hi",
        html="<p>hello</p>",
    )
    raw_bytes = base64.urlsafe_b64decode(payload["raw"])
    parsed = message_from_bytes(raw_bytes, policy=policy.default)

    assert parsed["From"] == "me@example.com"
    assert parsed["To"] == "you@example.com"
    assert parsed["Subject"] == "Hi"

    html_part = next(p for p in parsed.iter_parts() if p.get_content_type() == "text/html")
    assert "<p>hello</p>" in html_part.get_content()


@pytest.mark.unit
def test_load_gmail_credentials_rejects_blank_path() -> None:
    with pytest.raises(ValueError, match="client_secrets_path must be non-empty"):
        load_gmail_credentials(client_secrets_path="", token_path="/tmp/token.json")


@pytest.mark.unit
def test_load_gmail_credentials_uses_cached_token_when_valid(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Cached, still-valid token is loaded straight from disk — no OAuth flow runs."""
    token_file = os.path.join(str(tmp_path), "token.json")
    with open(token_file, "w") as fh:
        fh.write("{}")  # contents don't matter — Credentials.from_authorized_user_file is mocked

    cached = MagicMock(valid=True)
    with patch(
        "google.oauth2.credentials.Credentials.from_authorized_user_file",
        return_value=cached,
    ):
        result = load_gmail_credentials(
            client_secrets_path="/secrets/client.json",
            token_path=token_file,
        )
    assert result is cached


@pytest.mark.unit
def test_load_gmail_credentials_refreshes_expired_token(tmp_path: pytest.TempPathFactory) -> None:
    """Expired-but-refreshable creds take the refresh branch and re-write the cache."""
    token_file = os.path.join(str(tmp_path), "token.json")
    with open(token_file, "w") as fh:
        fh.write("{}")

    expired = MagicMock(valid=False, expired=True, refresh_token="refresh")
    expired.to_json.return_value = '{"refreshed": true}'

    def _refresh_marks_valid(_request: object) -> None:
        expired.valid = True

    expired.refresh.side_effect = _refresh_marks_valid

    with (
        patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_file",
            return_value=expired,
        ),
        patch("google.auth.transport.requests.Request"),
    ):
        result = load_gmail_credentials(
            client_secrets_path="/secrets/client.json",
            token_path=token_file,
        )
    assert result is expired
    expired.refresh.assert_called_once()
    with open(token_file) as fh:
        assert fh.read() == '{"refreshed": true}'


@pytest.mark.unit
def test_load_gmail_credentials_runs_local_server_when_no_token(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """No cached token → InstalledAppFlow.run_local_server is called and result is cached."""
    token_file = os.path.join(str(tmp_path), "token.json")  # does not exist yet

    minted = MagicMock(valid=True)
    minted.to_json.return_value = '{"new": true}'
    flow = MagicMock()
    flow.run_local_server.return_value = minted

    with patch(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
        return_value=flow,
    ):
        result = load_gmail_credentials(
            client_secrets_path="/secrets/client.json",
            token_path=token_file,
        )
    assert result is minted
    flow.run_local_server.assert_called_once_with(port=0)
    with open(token_file) as fh:
        assert fh.read() == '{"new": true}'


@pytest.mark.unit
def test_load_gmail_credentials_skips_caching_when_token_path_blank() -> None:
    """When token_path is empty, the freshly-minted creds are not written anywhere."""
    minted = MagicMock(valid=True)
    flow = MagicMock()
    flow.run_local_server.return_value = minted

    with (
        patch(
            "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
            return_value=flow,
        ),
        patch("builtins.open", mock_open()) as opener,
    ):
        result = load_gmail_credentials(
            client_secrets_path="/secrets/client.json",
            token_path="",
        )
    assert result is minted
    opener.assert_not_called()


@pytest.mark.unit
def test_build_gmail_service_calls_googleapiclient() -> None:
    creds = MagicMock(name="creds")
    fake_build = MagicMock(return_value=MagicMock(name="service"))
    with patch("googleapiclient.discovery.build", fake_build):
        service = build_gmail_service(creds)
    fake_build.assert_called_once_with("gmail", "v1", credentials=creds, cache_discovery=False)
    assert service is fake_build.return_value
