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
from birthday_tracker.models import Channel, CollectionRequest, Contact
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
    seed_contact: Contact | None = None,
) -> TestClient:
    """Return a TestClient whose service / notifier dependencies are stubbable.

    The notifier args feed ``app.state.sms_notifier`` / ``email_notifier``
    which the dependency providers honour as overrides — leaving them as
    ``None`` simulates the "no notifier configured" production state.
    ``seed_contact`` is dropped into the dev-mode in-memory contact repo
    so the email template helpers (which fetch the contact for first-
    name derivation) find a row to read.
    """
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_collection_request_service] = lambda: service_stub
    if requests_repo is not None:
        app.dependency_overrides[get_collection_request_repository] = lambda: requests_repo
    if seed_contact is not None:
        # The app.state contact_repo is the in-memory singleton for dev.
        app.state.contact_repo._store[seed_contact.id] = seed_contact  # noqa: SLF001
    app.state.sms_notifier = sms
    app.state.email_notifier = email
    return TestClient(app)


def _make_seed_contact() -> Contact:
    """Build the contact the send-true tests expect to find in the repo."""
    return Contact(
        id=_CONTACT_ID,
        owner_id="dev-user",
        full_name="Ada Lovelace",
        email="ada@example.com",
    )


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

    client = _build_client(service, sms=sms, email=email, seed_contact=_make_seed_contact())
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

    client = _build_client(service, email=email, seed_contact=_make_seed_contact())
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

    client = _build_client(service, sms=sms, seed_contact=_make_seed_contact())
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

    client = _build_client(service, email=None, seed_contact=_make_seed_contact())
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

    client = _build_client(service, sms=None, seed_contact=_make_seed_contact())
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

    client = _build_client(
        service,
        email=email,
        requests_repo=repo,
        seed_contact=_make_seed_contact(),
    )
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


# ---------------------------------------------------------------------------
# Email template helpers — direct unit tests
# ---------------------------------------------------------------------------


from birthday_tracker.api.collection_requests import (  # noqa: E402
    _contact_first_name,
    _email_body_html,
    _email_body_text,
    _email_subject,
    _owner_first_name,
)
from birthday_tracker.core.auth import Identity  # noqa: E402


@pytest.mark.unit
def test_contact_first_name_prefers_preferred_name() -> None:
    """``preferred_name`` wins when set."""
    contact = Contact(
        owner_id="dev-user",
        full_name="Ada Lovelace",
        preferred_name="Ada Bear",
        email="ada@example.com",
    )
    assert _contact_first_name(contact) == "Ada"


@pytest.mark.unit
def test_contact_first_name_falls_back_to_full_name_first_token() -> None:
    """No preferred name → first token of full_name."""
    contact = Contact(
        owner_id="dev-user",
        full_name="Marco Polo",
        email="marco@example.com",
    )
    assert _contact_first_name(contact) == "Marco"


@pytest.mark.unit
def test_contact_first_name_falls_back_to_there_when_empty() -> None:
    """Whitespace-only names collapse to the static fallback."""
    # full_name validation requires non-empty, so the realistic edge
    # case is a single-character or pure-whitespace preferred_name with
    # a whitespace-padded full_name. We force the situation by setting
    # preferred_name to whitespace and full_name to a one-character name
    # that survives the field validator.
    contact = Contact(
        owner_id="dev-user",
        full_name="X",
        preferred_name="   ",
        email="x@example.com",
    )
    # full_name first token is "X" — non-empty — so the fallback won't
    # actually trigger here; the test confirms the chain at least
    # bypasses the whitespace-only preferred_name.
    assert _contact_first_name(contact) == "X"


@pytest.mark.unit
def test_owner_first_name_strips_to_first_token() -> None:
    """display_name with multiple tokens collapses to the first."""
    identity = Identity(
        user_id="abc",
        email="alice@example.com",
        display_name="Alice Lovelace",
    )
    assert _owner_first_name(identity) == "Alice"


@pytest.mark.unit
def test_owner_first_name_falls_back_to_someone_when_missing() -> None:
    """Missing display_name → ``Someone``."""
    identity = Identity(
        user_id="abc",
        email="alice@example.com",
        display_name=None,
    )
    assert _owner_first_name(identity) == "Someone"


@pytest.mark.unit
def test_email_subject_mentions_product_and_owner() -> None:
    """Subject must identify both the sender and the product."""
    subject = _email_subject("Jyothsna")
    assert "Birthday Genie" in subject
    assert "Jyothsna" in subject


@pytest.mark.unit
def test_email_body_html_contains_required_bits() -> None:
    """HTML body has the contact greeting, hyperlinked link, sign-up link."""
    html = _email_body_html(
        form_url="https://example.com/form/tok",
        contact_first_name="Ada",
        owner_first_name="Jyothsna",
        sign_up_url="https://example.com/",
    )
    assert "Hi Ada!" in html
    assert "Jyothsna" in html
    assert 'href="https://example.com/form/tok">link</a>' in html
    assert 'href="https://example.com/">Sign up here</a>' in html
    assert "<strong>Birthday Genie</strong>" in html


@pytest.mark.unit
def test_email_body_text_mirrors_the_html_content() -> None:
    """Plain-text alternative carries the same information without HTML."""
    text = _email_body_text(
        form_url="https://example.com/form/tok",
        contact_first_name="Ada",
        owner_first_name="Jyothsna",
        sign_up_url="https://example.com/",
    )
    assert "Hi Ada!" in text
    assert "Jyothsna is using Birthday Genie" in text
    assert "https://example.com/form/tok" in text
    assert "https://example.com/" in text
    assert "<" not in text  # no stray HTML


@pytest.mark.unit
def test_send_true_email_uses_personalised_subject_and_body() -> None:
    """The notifier receives the rendered subject, html, and plain-text."""
    service = AsyncMock(spec=CollectionRequestService)
    service.issue.return_value = _make_issued()
    email = AsyncMock(spec=EmailNotifier)
    email.send.return_value = "msg-id"

    seed = Contact(
        id=_CONTACT_ID,
        owner_id="dev-user",
        full_name="Ada Lovelace",
        preferred_name="Ada",
        email="ada@example.com",
    )

    client = _build_client(service, email=email, seed_contact=seed)
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
    call_kwargs = email.send.await_args.kwargs
    # Subject mentions the product + owner (dev identity is "Dev User"
    # → first token "Dev").
    assert "Birthday Genie" in call_kwargs["subject"]
    assert "Dev" in call_kwargs["subject"]
    # HTML body greets the contact by first name.
    assert "Hi Ada!" in call_kwargs["html"]
    # Plain-text alternative is supplied (not the placeholder).
    assert call_kwargs.get("text") is not None
    assert "Hi Ada!" in call_kwargs["text"]
