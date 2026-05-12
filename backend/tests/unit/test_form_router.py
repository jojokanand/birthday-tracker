"""Unit tests for GET /form/{token} and POST /form/{token}.

The service layer and rate limiter are replaced by stubs so these tests stay
fast and dependency-free.  They verify HTTP semantics — status codes, response
shapes, header behaviour, and error mapping — not business logic.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.api.dependencies import (
    get_collection_request_service,
    get_form_rate_limiter,
)
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.core.rate_limit import RateLimiter, RateLimitExceeded
from birthday_tracker.core.tokens import TokenExpired, TokenInvalid
from birthday_tracker.main import create_app
from birthday_tracker.models import Channel, CollectionRequest, Contact
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
    RequestNotPending,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_TOKEN = "payload.sig"  # noqa: S105  (test-only fake token)
_CONTACT_ID = uuid4()
_REQUEST_ID = uuid4()
_EXPIRES_AT = dt.datetime(2030, 1, 1, tzinfo=dt.UTC)


def _make_request(channel: Channel = Channel.email) -> CollectionRequest:
    return CollectionRequest(
        id=_REQUEST_ID,
        contact_id=_CONTACT_ID,
        channel=channel,
        destination="ada@example.com",
        token_hash="a" * 64,
        expires_at=_EXPIRES_AT,
    )


def _make_contact(preferred_name: str | None = "Ada") -> Contact:
    return Contact(
        id=_CONTACT_ID,
        full_name="Ada Lovelace",
        preferred_name=preferred_name,
        email="ada@example.com",
    )


def _permissive_limiter() -> RateLimiter:
    """Return a RateLimiter stub whose .hit() never raises."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.hit.return_value = None
    return limiter


def _blocking_limiter() -> RateLimiter:
    """Return a RateLimiter stub that always raises RateLimitExceeded."""
    limiter = MagicMock(spec=RateLimiter)
    limiter.hit.side_effect = RateLimitExceeded("limit hit")
    return limiter


def _build_client(
    service_stub: CollectionRequestService,
    limiter: RateLimiter | None = None,
) -> TestClient:
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_collection_request_service] = lambda: service_stub
    app.dependency_overrides[get_form_rate_limiter] = lambda: (
        limiter if limiter is not None else _permissive_limiter()
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /form/{token}
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_form_returns_200_with_metadata() -> None:
    """Happy path: valid token → 200 with greeting_name, channel, expires_at."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.return_value = _make_request()
    service.contacts = AsyncMock()
    service.contacts.get.return_value = _make_contact()

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["greeting_name"] == "Ada"
    assert body["channel"] == "email"
    assert body["expires_at"] == _EXPIRES_AT.isoformat()


@pytest.mark.unit
def test_get_form_uses_there_when_contact_missing() -> None:
    """When the contact row is gone the greeting falls back to 'there'."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.return_value = _make_request()
    service.contacts = AsyncMock()
    service.contacts.get.return_value = None

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 200
    assert resp.json()["greeting_name"] == "there"


@pytest.mark.unit
def test_get_form_uses_there_when_preferred_name_is_none() -> None:
    """A contact with no preferred_name also falls back to 'there'."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.return_value = _make_request()
    service.contacts = AsyncMock()
    service.contacts.get.return_value = _make_contact(preferred_name=None)

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 200
    assert resp.json()["greeting_name"] == "there"


@pytest.mark.unit
def test_get_form_returns_404_for_invalid_token() -> None:
    """TokenInvalid from the service maps to 404 to avoid oracle attacks."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.side_effect = TokenInvalid("bad signature")

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 404
    body = resp.json()
    assert body["title"] == "Form not found"


@pytest.mark.unit
def test_get_form_returns_410_for_expired_token() -> None:
    """TokenExpired maps to 410 Gone."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.side_effect = TokenExpired("token expired")

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 410
    body = resp.json()
    assert body["title"] == "Form no longer available"


@pytest.mark.unit
def test_get_form_returns_410_for_already_fulfilled() -> None:
    """RequestNotPending (already fulfilled) maps to 410 Gone."""
    service = AsyncMock(spec=CollectionRequestService)
    service.lookup.side_effect = RequestNotPending("already fulfilled")

    client = _build_client(service)
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 410


@pytest.mark.unit
def test_get_form_returns_429_when_rate_limited() -> None:
    """RateLimitExceeded before hitting the service maps to 429."""
    service = AsyncMock(spec=CollectionRequestService)

    client = _build_client(service, limiter=_blocking_limiter())
    resp = client.get(f"/form/{_TOKEN}")

    assert resp.status_code == 429
    body = resp.json()
    assert body["title"] == "Too many requests"
    service.lookup.assert_not_called()


# ---------------------------------------------------------------------------
# POST /form/{token}
# ---------------------------------------------------------------------------

_VALID_BODY = {
    "full_name": "Ada Lovelace",
    "preferred_name": "Ada",
    "address": {"street1": "1 Main St", "city": "London", "country": "GB"},
    "birthday": {"month": 12, "day": 10, "year": 1990},
}


@pytest.mark.unit
def test_post_form_returns_204_on_success() -> None:
    """Happy path: valid token + valid body → 204 No Content."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.return_value = _make_contact()

    client = _build_client(service)
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.unit
def test_post_form_returns_204_without_optional_fields() -> None:
    """preferred_name is optional; birthday year is optional."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.return_value = _make_contact()

    client = _build_client(service)
    body = {
        "full_name": "Ada Lovelace",
        "address": {"street1": "1 Main St", "city": "London", "country": "GB"},
        "birthday": {"month": 12, "day": 10},
    }
    resp = client.post(f"/form/{_TOKEN}", json=body)

    assert resp.status_code == 204


@pytest.mark.unit
def test_post_form_returns_422_for_missing_full_name() -> None:
    """full_name is required in the form body."""
    service = AsyncMock(spec=CollectionRequestService)
    client = _build_client(service)

    body = dict(_VALID_BODY)
    del body["full_name"]
    resp = client.post(f"/form/{_TOKEN}", json=body)

    assert resp.status_code == 422
    service.fulfill.assert_not_called()


@pytest.mark.unit
def test_post_form_returns_404_for_invalid_token() -> None:
    """TokenInvalid from service.fulfill maps to 404."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.side_effect = TokenInvalid("bad sig")

    client = _build_client(service)
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 404
    assert resp.json()["title"] == "Form not found"


@pytest.mark.unit
def test_post_form_returns_410_for_expired_token() -> None:
    """TokenExpired from service.fulfill maps to 410."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.side_effect = TokenExpired("expired")

    client = _build_client(service)
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 410


@pytest.mark.unit
def test_post_form_returns_410_for_already_fulfilled() -> None:
    """RequestNotPending from service.fulfill maps to 410."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.side_effect = RequestNotPending("already used")

    client = _build_client(service)
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 410


@pytest.mark.unit
def test_post_form_returns_404_when_contact_deleted() -> None:
    """ContactNotFound from service.fulfill maps to 404."""
    service = AsyncMock(spec=CollectionRequestService)
    service.fulfill.side_effect = ContactNotFound("contact gone")

    client = _build_client(service)
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 404
    assert resp.json()["title"] == "Contact not found"


@pytest.mark.unit
def test_post_form_returns_429_when_rate_limited() -> None:
    """Rate limit exceeded before calling service.fulfill → 429."""
    service = AsyncMock(spec=CollectionRequestService)

    client = _build_client(service, limiter=_blocking_limiter())
    resp = client.post(f"/form/{_TOKEN}", json=_VALID_BODY)

    assert resp.status_code == 429
    assert resp.json()["title"] == "Too many requests"
    service.fulfill.assert_not_called()
