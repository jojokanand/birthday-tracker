"""Unit tests for POST /collection-requests.

The service layer is replaced by a lightweight stub so these tests never touch
Firestore.  They verify HTTP semantics — status codes, response shapes, and
error mapping — not business logic (which lives in
:mod:`tests.unit.services.test_collection_requests`).
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.adapters import InMemoryCollectionRequestRepository
from birthday_tracker.api.dependencies import (
    get_collection_request_repository,
    get_collection_request_service,
)
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app
from birthday_tracker.models import Channel, CollectionRequest
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
    IssuedRequest,
)
from birthday_tracker.services.notifiers import (
    EmailNotifier,
    NotificationError,
    SmsNotifier,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_CONTACT_ID: UUID = uuid4()
_REQUEST_ID: UUID = uuid4()
_TOKEN = "payload.sig"  # noqa: S105  (test-only fake token)
_FORM_URL = f"https://example.test/form/{_TOKEN}"
_EXPIRES_AT = dt.datetime(2030, 1, 1, tzinfo=dt.UTC)


def _make_request(contact_id: UUID = _CONTACT_ID) -> CollectionRequest:
    """Build a minimal CollectionRequest for stubbing."""
    return CollectionRequest(
        id=_REQUEST_ID,
        owner_id="dev-user",
        contact_id=contact_id,
        channel=Channel.email,
        destination="ada@example.com",
        token_hash="a" * 64,
        expires_at=_EXPIRES_AT,
    )


def _make_issued(contact_id: UUID = _CONTACT_ID) -> IssuedRequest:
    """Build a minimal IssuedRequest for stubbing."""
    return IssuedRequest(
        request=_make_request(contact_id),
        token=_TOKEN,
        url=_FORM_URL,
    )


def _build_client(
    service_stub: CollectionRequestService,
    *,
    sms: SmsNotifier | None = None,
    email: EmailNotifier | None = None,
    requests_repo: InMemoryCollectionRequestRepository | None = None,
) -> TestClient:
    """Return a TestClient whose service / notifier dependencies are stubbable.

    The notifier args feed ``app.state.sms_notifier`` / ``email_notifier``
    which the dependency providers honour as overrides — leaving them as
    ``None`` simulates the "no notifier configured" production state.
    """
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_collection_request_service] = lambda: service_stub
    if requests_repo is not None:
        app.dependency_overrides[get_collection_request_repository] = lambda: requests_repo
    app.state.sms_notifier = sms
    app.state.email_notifier = email
    return TestClient(app)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_issue_returns_201_with_body() -> None:
    """Happy path: valid body → 201 with all fields populated."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()

    client = _build_client(service)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "email",
            "destination": "ada@example.com",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["request_id"] == str(_REQUEST_ID)
    assert body["contact_id"] == str(_CONTACT_ID)
    assert body["channel"] == "email"
    assert body["destination"] == "ada@example.com"
    assert body["form_url"] == _FORM_URL
    assert body["expires_at"] == _EXPIRES_AT.isoformat()


@pytest.mark.unit
def test_issue_returns_404_when_contact_missing() -> None:
    """ContactNotFound from the service maps to 404 problem+json."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.side_effect = ContactNotFound("contact abc not found")

    client = _build_client(service)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(uuid4()),
            "channel": "sms",
            "destination": "+15550001234",
        },
    )

    assert resp.status_code == 404
    body = resp.json()
    assert body["title"] == "Contact not found"
    assert body["status"] == 404


@pytest.mark.unit
def test_issue_returns_422_for_missing_fields() -> None:
    """An incomplete body triggers request-validation failure (422)."""
    service = AsyncMock(spec=CollectionRequestService)
    client = _build_client(service)

    resp = client.post("/collection-requests", json={"channel": "email"})

    assert resp.status_code == 422
    service.issue.assert_not_called()


@pytest.mark.unit
def test_issue_returns_422_for_blank_destination() -> None:
    """destination must be non-empty (min_length=1)."""
    service = AsyncMock(spec=CollectionRequestService)
    client = _build_client(service)

    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(uuid4()),
            "channel": "email",
            "destination": "",
        },
    )

    assert resp.status_code == 422
    service.issue.assert_not_called()


@pytest.mark.unit
def test_issue_returns_422_for_invalid_channel() -> None:
    """An unrecognised channel value triggers 422."""
    service = AsyncMock(spec=CollectionRequestService)
    client = _build_client(service)

    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(uuid4()),
            "channel": "carrier_pigeon",
            "destination": "somewhere",
        },
    )

    assert resp.status_code == 422
    service.issue.assert_not_called()


@pytest.mark.unit
def test_issue_accepts_sms_channel() -> None:
    """sms is a valid Channel value."""
    service = AsyncMock(spec=CollectionRequestService)
    contact_id = uuid4()
    issued = IssuedRequest(
        request=CollectionRequest(
            id=uuid4(),
            owner_id="dev-user",
            contact_id=contact_id,
            channel=Channel.sms,
            destination="+15550001234",
            token_hash="b" * 64,
            expires_at=_EXPIRES_AT,
        ),
        token=_TOKEN,
        url=_FORM_URL,
    )
    service.issue.return_value = issued

    client = _build_client(service)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(contact_id),
            "channel": "sms",
            "destination": "+15550001234",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["channel"] == "sms"


# ---------------------------------------------------------------------------
# `send=True` mode — notifier delivery, rollback, missing-config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_issue_default_send_false_does_not_call_notifier() -> None:
    """``send`` defaults to ``False`` and ``sent`` echoes that on the response."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()
    sms = AsyncMock(spec=SmsNotifier)
    email = AsyncMock(spec=EmailNotifier)

    client = _build_client(service, sms=sms, email=email)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "email",
            "destination": "ada@example.com",
        },
    )

    assert resp.status_code == 201
    assert resp.json()["sent"] is False
    sms.send.assert_not_called()
    email.send.assert_not_called()


@pytest.mark.unit
def test_issue_send_true_email_calls_email_notifier() -> None:
    """``send=true`` + email channel → backend calls the EmailNotifier and reports sent=true."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()
    email = AsyncMock(spec=EmailNotifier)
    email.send.return_value = "msg-id"

    client = _build_client(service, email=email)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "email",
            "destination": "ada@example.com",
            "send": True,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["sent"] is True
    email.send.assert_awaited_once()
    sent_args = email.send.await_args
    assert sent_args.kwargs["to"] == "ada@example.com"
    assert _FORM_URL in sent_args.kwargs["html"]


@pytest.mark.unit
def test_issue_send_true_sms_calls_sms_notifier() -> None:
    """``send=true`` + SMS channel → backend calls the SmsNotifier."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued(_CONTACT_ID)
    sms = AsyncMock(spec=SmsNotifier)
    sms.send.return_value = "SMxxx"

    client = _build_client(service, sms=sms)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "sms",
            "destination": "+15550001234",
            "send": True,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["sent"] is True
    sms.send.assert_awaited_once()
    sent_args = sms.send.await_args
    assert sent_args.kwargs["to"] == "+15550001234"
    assert _FORM_URL in sent_args.kwargs["body"]


@pytest.mark.unit
def test_issue_send_true_returns_503_when_email_not_configured() -> None:
    """``send=true`` for email with no notifier wired → 503 problem+json."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()

    client = _build_client(service, email=None)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "email",
            "destination": "ada@example.com",
            "send": True,
        },
    )

    assert resp.status_code == 503
    assert resp.json()["title"] == "Email delivery is not configured"


@pytest.mark.unit
def test_issue_send_true_returns_503_when_sms_not_configured() -> None:
    """``send=true`` for sms with no notifier wired → 503 problem+json."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()

    client = _build_client(service, sms=None)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "sms",
            "destination": "+15550001234",
            "send": True,
        },
    )

    assert resp.status_code == 503
    assert resp.json()["title"] == "SMS delivery is not configured"


@pytest.mark.unit
async def test_issue_rolls_back_persisted_request_on_notifier_failure() -> None:
    """Notifier failure → 502 + persisted request is deleted from the repo."""
    repo = InMemoryCollectionRequestRepository()
    # Pre-seed the repo with what the (real) service would have written
    # so we can assert the route deletes it on the rollback path.
    persisted = _make_request()
    await repo.save(persisted)
    assert await repo.get(persisted.id, "dev-user") is not None

    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()
    email = AsyncMock(spec=EmailNotifier)
    email.send.side_effect = NotificationError("Gmail rejected the send")

    client = _build_client(service, email=email, requests_repo=repo)
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(_CONTACT_ID),
            "channel": "email",
            "destination": "ada@example.com",
            "send": True,
        },
    )

    assert resp.status_code == 502
    assert resp.json()["title"] == "Notification provider rejected the send"
    # The route deleted the persisted request so a retry mints a fresh one.
    assert await repo.get(persisted.id, "dev-user") is None
