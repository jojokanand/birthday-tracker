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

from birthday_tracker.api.dependencies import get_collection_request_service
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app
from birthday_tracker.models import Channel, CollectionRequest
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
    IssuedRequest,
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


def _build_client(service_stub: CollectionRequestService) -> TestClient:
    """Return a TestClient whose service dependency is replaced by *service_stub*."""
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_collection_request_service] = lambda: service_stub
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
