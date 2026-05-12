"""End-to-end integration tests for the collection-request form flow.

These tests drive the full HTTP stack (FastAPI TestClient) against real
in-memory adapters — no Firestore emulator required.  They exercise the
happy path and key error paths across the three routers involved:

  POST /collection-requests → issue a token
  GET  /form/{token}        → read form metadata
  POST /form/{token}        → submit the form
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.adapters import (
    InMemoryCollectionRequestRepository,
    InMemoryContactRepository,
)
from birthday_tracker.api.dependencies import (
    get_collection_request_service,
    get_form_rate_limiter,
)
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.core.rate_limit import RateLimiter
from birthday_tracker.main import create_app
from birthday_tracker.models import Channel, Contact
from birthday_tracker.services.collection_requests import CollectionRequestService

_TOKEN_SECRET = "integration-test-secret"
_BASE_URL = "https://example.test"


@pytest.fixture
def contacts() -> InMemoryContactRepository:
    """A fresh in-memory contact store."""
    return InMemoryContactRepository()


@pytest.fixture
def requests_repo() -> InMemoryCollectionRequestRepository:
    """A fresh in-memory collection-request store."""
    return InMemoryCollectionRequestRepository()


@pytest.fixture
def service(
    contacts: InMemoryContactRepository,
    requests_repo: InMemoryCollectionRequestRepository,
) -> CollectionRequestService:
    """A wired :class:`CollectionRequestService` backed by in-memory repos."""
    return CollectionRequestService(
        contacts=contacts,
        requests=requests_repo,
        token_secret=_TOKEN_SECRET,
        token_ttl_seconds=3600,
        public_base_url=_BASE_URL,
    )


@pytest.fixture
def client(service: CollectionRequestService) -> TestClient:
    """TestClient with in-memory adapters and a permissive rate limiter."""
    get_settings_dep.cache_clear()
    app = create_app(
        settings=Settings(
            app_env=AppEnv.development,
            log_level="ERROR",
            form_token_secret=_TOKEN_SECRET,
            public_base_url=_BASE_URL,
        )
    )
    app.dependency_overrides[get_collection_request_service] = lambda: service
    app.dependency_overrides[get_form_rate_limiter] = lambda: RateLimiter(
        max_per_window=100, window_seconds=60.0
    )
    return TestClient(app)


@pytest.fixture
async def contact(contacts: InMemoryContactRepository) -> Contact:
    """Persist and return a test contact owned by the dev identity."""
    c = Contact(
        owner_id="dev-user",
        full_name="Ada Lovelace",
        preferred_name="Ada",
        email="ada@example.com",
    )
    await contacts.save(c)
    return c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_VALID_SUBMISSION = {
    "full_name": "Ada Lovelace",
    "preferred_name": "Ada",
    "address": {"street1": "1 Main St", "city": "London", "country": "GB"},
    "birthday": {"month": 12, "day": 10, "year": 1990},
}


def _issue(client: TestClient, contact: Contact) -> str:
    """Issue a collection request and return the raw token."""
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(contact.id),
            "channel": "email",
            "destination": "ada@example.com",
        },
    )
    assert resp.status_code == 201
    form_url: str = resp.json()["form_url"]
    return form_url.split("/form/")[-1]


# ---------------------------------------------------------------------------
# Full happy-path flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_full_flow(client: TestClient, contact: Contact) -> None:
    """Issue → GET form → POST form → token is consumed (410 on reuse)."""
    token = _issue(client, contact)

    # Contact opens the form link
    get_resp = client.get(f"/form/{token}")
    assert get_resp.status_code == 200
    meta = get_resp.json()
    assert meta["greeting_name"] == "Ada"
    assert meta["channel"] == "email"

    # Contact submits
    submit_resp = client.post(f"/form/{token}", json=_VALID_SUBMISSION)
    assert submit_resp.status_code == 204

    # Re-submit is rejected (request is now fulfilled)
    resubmit = client.post(f"/form/{token}", json=_VALID_SUBMISSION)
    assert resubmit.status_code == 410


@pytest.mark.integration
async def test_issue_response_shape(client: TestClient, contact: Contact) -> None:
    """POST /collection-requests returns all expected fields."""
    resp = client.post(
        "/collection-requests",
        json={
            "contact_id": str(contact.id),
            "channel": "sms",
            "destination": "+15550001234",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["contact_id"] == str(contact.id)
    assert body["channel"] == "sms"
    assert body["destination"] == "+15550001234"
    assert body["form_url"].startswith(f"{_BASE_URL}/form/")
    assert "request_id" in body
    assert "expires_at" in body


@pytest.mark.integration
async def test_get_form_returns_410_after_fulfillment(client: TestClient, contact: Contact) -> None:
    """GET /form/{token} returns 410 once the form has been submitted."""
    token = _issue(client, contact)
    client.post(f"/form/{token}", json=_VALID_SUBMISSION)

    resp = client.get(f"/form/{token}")
    assert resp.status_code == 410


@pytest.mark.integration
async def test_issue_for_missing_contact_returns_404(client: TestClient) -> None:
    """POST /collection-requests with an unknown contact_id → 404."""
    resp = client.post(
        "/collection-requests",
        json={"contact_id": str(uuid.uuid4()), "channel": "email", "destination": "x@y.com"},
    )
    assert resp.status_code == 404
    assert resp.json()["title"] == "Contact not found"


@pytest.mark.integration
async def test_get_form_with_invalid_token_returns_404(client: TestClient) -> None:
    """GET /form/{garbage} → 404 (we don't leak whether a token would be valid)."""
    resp = client.get("/form/not.a.real.token")
    assert resp.status_code == 404


@pytest.mark.integration
async def test_submit_form_with_invalid_token_returns_404(client: TestClient) -> None:
    """POST /form/{garbage} → 404."""
    resp = client.post("/form/bad.token", json=_VALID_SUBMISSION)
    assert resp.status_code == 404


@pytest.mark.integration
async def test_rate_limit_blocks_excess_requests(
    contacts: InMemoryContactRepository,
    requests_repo: InMemoryCollectionRequestRepository,
) -> None:
    """After hitting the per-token cap, /form/* returns 429."""
    c = Contact(owner_id="dev-user", full_name="Test", email="t@example.com")
    await contacts.save(c)

    svc = CollectionRequestService(
        contacts=contacts,
        requests=requests_repo,
        token_secret=_TOKEN_SECRET,
        token_ttl_seconds=3600,
        public_base_url=_BASE_URL,
    )
    issued = await svc.issue(
        contact_id=c.id,
        channel=Channel.email,
        destination="t@example.com",
        owner_id="dev-user",
    )
    token = issued.token

    get_settings_dep.cache_clear()
    app = create_app(
        settings=Settings(
            app_env=AppEnv.development,
            log_level="ERROR",
            form_token_secret=_TOKEN_SECRET,
            public_base_url=_BASE_URL,
        )
    )
    app.dependency_overrides[get_collection_request_service] = lambda: svc
    tight_limiter = RateLimiter(max_per_window=2, window_seconds=60.0)
    app.dependency_overrides[get_form_rate_limiter] = lambda: tight_limiter

    with TestClient(app) as tight_client:
        tight_client.get(f"/form/{token}")  # request 1
        tight_client.get(f"/form/{token}")  # request 2
        r3 = tight_client.get(f"/form/{token}")  # request 3 — over limit
        assert r3.status_code == 429
        assert r3.json()["title"] == "Too many requests"
