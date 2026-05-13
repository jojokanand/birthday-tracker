"""Gmail-API-backed email notifier.

Sends mail as the owner's own Gmail user via OAuth 2.0 with the
``gmail.send`` scope. The first run requires an interactive browser flow to
mint a refresh token (see :func:`load_gmail_credentials` and the README for
the bootstrap procedure); subsequent runs reuse the cached token file.

The Google API Python client is synchronous, so the actual HTTP send is
dispatched to a worker thread via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import base64
from email.message import EmailMessage
from typing import TYPE_CHECKING, Any

from birthday_tracker.core.logging import get_logger
from birthday_tracker.services.notifiers import NotificationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from google.oauth2.credentials import Credentials

logger = get_logger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_gmail_credentials(
    client_secrets_path: str = "",
    token_path: str = "",
    token_json: str = "",
) -> Credentials:
    """Load (or interactively mint) Gmail OAuth credentials.

    Three modes, in priority order:

    1. ``token_json`` set — parse the credentials directly from the JSON
       string. Used in production where the refresh token is mounted as
       a Secret Manager env var rather than a file (Cloud Run has no
       writable persistent disk).
    2. ``token_path`` exists on disk — load cached credentials from the
       file. The default for local development.
    3. Otherwise — fall back to the interactive OAuth flow, requiring
       ``client_secrets_path`` to be set. Writes the new token to
       ``token_path`` for next time.

    Expired credentials with a refresh token are refreshed in place
    (and re-written to disk when ``token_path`` is set).

    Args:
        client_secrets_path: Path to the OAuth client_secret.json
            downloaded from the GCP Console. Required only when the
            interactive flow has to run.
        token_path: Path where the refresh token is cached on disk.
        token_json: Raw token JSON content (e.g. read from an env var
            or Secret Manager). Takes precedence over ``token_path``.

    Returns:
        A :class:`google.oauth2.credentials.Credentials` ready to use
        with the Gmail API client.

    Raises:
        ValueError: When none of the three modes can produce credentials —
            specifically, ``token_json`` is empty, ``token_path`` does
            not exist, and ``client_secrets_path`` is also empty so the
            interactive flow can't run.
    """
    import json  # noqa: PLC0415
    import os  # noqa: PLC0415

    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

    creds: Credentials | None = None
    if token_json:
        # google-auth's typing for from_authorized_user_info is stubbed
        # incompletely; runtime contract is well-defined.
        creds = Credentials.from_authorized_user_info(  # type: ignore[no-untyped-call]
            json.loads(token_json), GMAIL_SCOPES
        )
    elif token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            token_path, GMAIL_SCOPES
        )

    if creds is None or not creds.valid:
        if creds is not None and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # type: ignore[no-untyped-call]
        else:
            if not client_secrets_path:
                raise ValueError(
                    "Cannot mint Gmail credentials: token_json / token_path "
                    "missing or invalid, and client_secrets_path not set so "
                    "the interactive OAuth flow can't run."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        # Persist refreshed creds back to disk only when we have a
        # writable cache location and were not given raw JSON content
        # (Cloud Run has no writable disk for the JSON-content path).
        if token_path and not token_json:
            with open(token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
    return creds


def build_gmail_service(credentials: Credentials) -> Any:
    """Construct the Gmail API service client.

    Args:
        credentials: Credentials from :func:`load_gmail_credentials`.

    Returns:
        A Gmail API ``users()`` resource. Typed as :data:`Any` because the
        google-api-python-client is dynamically generated.
    """
    from googleapiclient.discovery import build  # noqa: PLC0415

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _encode_email(from_addr: str, to: str, subject: str, html: str) -> dict[str, str]:
    """Build a base64url-encoded MIME message ready for the Gmail API.

    Args:
        from_addr: Sender address, must match the OAuth grant.
        to: Recipient address.
        subject: Subject line (no newlines).
        html: HTML body.

    Returns:
        ``{"raw": ...}`` payload accepted by ``users().messages().send``.
    """
    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = to
    message["Subject"] = subject
    message.set_content("This message contains HTML; please use an HTML-capable client.")
    message.add_alternative(html, subtype="html")

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": encoded}


class GmailNotifier:
    """A :class:`~birthday_tracker.services.EmailNotifier` backed by the Gmail API.

    Attributes:
        service: Gmail API service client (from :func:`build_gmail_service`).
        from_address: Email address mail is sent from. Must match the OAuth
            grant or Gmail will reject the send.
    """

    def __init__(self, service: Any, from_address: str) -> None:
        """Build the notifier.

        Args:
            service: Gmail API service client.
            from_address: Sender email address.

        Raises:
            ValueError: If ``from_address`` is empty.
        """
        if not from_address:
            raise ValueError("from_address must be non-empty")
        self.service = service
        self.from_address = from_address

    async def send(self, to: str, subject: str, html: str) -> str:
        """Send an HTML email via Gmail.

        Args:
            to: Recipient email address.
            subject: Subject line.
            html: HTML body.

        Returns:
            The Gmail message ID assigned by the API.

        Raises:
            NotificationError: Wraps any exception raised by the Gmail API.
        """
        payload = _encode_email(self.from_address, to, subject, html)
        try:
            sent = await asyncio.to_thread(
                lambda: self.service.users().messages().send(userId="me", body=payload).execute(),
            )
        except Exception as exc:  # noqa: BLE001 - SDK can raise many types
            logger.warning("gmail_send_failed", to=to, error=str(exc))
            raise NotificationError(f"Gmail send failed: {exc}") from exc

        message_id: str = sent["id"]
        logger.info("gmail_sent", to=to, message_id=message_id)
        return message_id
