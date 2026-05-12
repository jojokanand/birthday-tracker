"""Unit tests for the digest router.

OIDC validation is bypassed by leaving ``digest_oidc_audience`` empty.
Gmail send paths are patched so no external services are touched.

Multi-tenant change: ``POST /internal/digest/send`` iterates the user
repository and delivers per-user digests. Tests seed users via the
in-memory ``UserRepository`` dependency override.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.adapters import (
    InMemoryContactRepository,
    InMemoryUserRepository,
)
from birthday_tracker.api.dependencies import (
    get_contact_repository,
    get_user_repository,
)
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app
from birthday_tracker.models import Contact, User
from birthday_tracker.models.birthday import Birthday

OWNER_A = "owner-a"
OWNER_B = "owner-b"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client(
    contacts: InMemoryContactRepository | None = None,
    users: InMemoryUserRepository | None = None,
    extra_settings: dict[str, str] | None = None,
) -> TestClient:
    """Return a :class:`TestClient` with the repos injected and digest settings applied."""
    get_settings_dep.cache_clear()
    kwargs: dict[str, str] = {
        "app_env": AppEnv.development,
        "log_level": "ERROR",
        # Leave digest_oidc_audience empty → OIDC auth skipped in tests.
        "gmail_from_address": "owner@example.com",
        **(extra_settings or {}),
    }
    app = create_app(settings=Settings(**kwargs))  # type: ignore[arg-type]
    if contacts is not None:
        app.dependency_overrides[get_contact_repository] = lambda: contacts
    if users is not None:
        app.dependency_overrides[get_user_repository] = lambda: users
    return TestClient(app)


async def _seed_contact(
    repo: InMemoryContactRepository,
    *,
    full_name: str = "Ada Lovelace",
    email: str | None = "ada@example.com",
    birthday: Birthday | None = None,
    owner_id: str = OWNER_A,
) -> Contact:
    contact = Contact(owner_id=owner_id, full_name=full_name, email=email, birthday=birthday)
    await repo.save(contact)
    return contact


async def _seed_user(
    repo: InMemoryUserRepository,
    *,
    user_id: str,
    email: str,
    digest_owner_email: str | None = None,
) -> User:
    user = User(id=user_id, email=email, digest_owner_email=digest_owner_email)
    await repo.save(user)
    return user


# ---------------------------------------------------------------------------
# GET /internal/digest/upcoming
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetUpcoming:
    """Tests for ``GET /internal/digest/upcoming?owner_id=...``."""

    @pytest.mark.asyncio
    async def test_empty_repo(self) -> None:
        """Returns an empty list when the owner has no contacts."""
        contacts = InMemoryContactRepository()
        client = _build_client(contacts=contacts)
        resp = client.get("/internal/digest/upcoming", params={"owner_id": OWNER_A})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["items"] == []
        assert body["owner_id"] == OWNER_A

    @pytest.mark.asyncio
    async def test_contact_within_window(self) -> None:
        """A contact with a birthday within the default 14-day window is returned."""
        today = dt.date.today()
        soon = today + dt.timedelta(days=3)
        contacts = InMemoryContactRepository()
        await _seed_contact(contacts, birthday=Birthday(month=soon.month, day=soon.day))
        client = _build_client(contacts=contacts)

        resp = client.get(
            "/internal/digest/upcoming",
            params={"owner_id": OWNER_A, "days": 14},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["items"][0]["days_until"] == 3

    @pytest.mark.asyncio
    async def test_other_owners_contacts_excluded(self) -> None:
        """Cross-tenant isolation in the admin endpoint too."""
        today = dt.date.today()
        soon = today + dt.timedelta(days=3)
        contacts = InMemoryContactRepository()
        await _seed_contact(
            contacts,
            birthday=Birthday(month=soon.month, day=soon.day),
            owner_id=OWNER_B,  # belongs to a different user
        )
        client = _build_client(contacts=contacts)

        resp = client.get("/internal/digest/upcoming", params={"owner_id": OWNER_A})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_default_days_is_14(self) -> None:
        """The default look-ahead window is 14 days."""
        contacts = InMemoryContactRepository()
        client = _build_client(contacts=contacts)
        resp = client.get("/internal/digest/upcoming", params={"owner_id": OWNER_A})
        assert resp.status_code == 200
        assert resp.json()["days"] == 14

    @pytest.mark.asyncio
    async def test_owner_id_required(self) -> None:
        """Missing owner_id → 422 from FastAPI validation."""
        contacts = InMemoryContactRepository()
        client = _build_client(contacts=contacts)
        resp = client.get("/internal/digest/upcoming")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /internal/digest/send
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSendDigest:
    """Tests for ``POST /internal/digest/send``."""

    @pytest.mark.asyncio
    async def test_no_users_means_no_deliveries(self) -> None:
        """An empty user repo yields a 200 with zero deliveries — not an error."""
        contacts = InMemoryContactRepository()
        users = InMemoryUserRepository()
        client = _build_client(contacts=contacts, users=users)

        mock_notifier = AsyncMock()
        mock_notifier.send = AsyncMock(return_value="msg-1")
        with (
            patch(
                "birthday_tracker.adapters.load_gmail_credentials",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.build_gmail_service",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.GmailNotifier",
                return_value=mock_notifier,
            ),
        ):
            resp = client.post("/internal/digest/send")

        assert resp.status_code == 200
        body = resp.json()
        assert body["delivered"] == 0
        assert body["users"] == []

    @pytest.mark.asyncio
    async def test_fans_out_per_user(self) -> None:
        """One email per known user, each scoped to their own contacts."""
        contacts = InMemoryContactRepository()
        users = InMemoryUserRepository()
        today = dt.date(2024, 6, 15)
        await _seed_contact(
            contacts,
            full_name="A's Friend",
            email="af@example.com",
            birthday=Birthday(month=6, day=18),  # 3 days
            owner_id=OWNER_A,
        )
        await _seed_contact(
            contacts,
            full_name="B's Friend",
            email="bf@example.com",
            birthday=Birthday(month=6, day=20),  # 5 days
            owner_id=OWNER_B,
        )
        await _seed_user(users, user_id=OWNER_A, email="a@example.com")
        await _seed_user(
            users,
            user_id=OWNER_B,
            email="b@example.com",
            digest_owner_email="b-shared@example.com",
        )
        client = _build_client(contacts=contacts, users=users)

        mock_notifier = AsyncMock()
        mock_notifier.send = AsyncMock(return_value="msg")
        with (
            patch(
                "birthday_tracker.adapters.load_gmail_credentials",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.build_gmail_service",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.GmailNotifier",
                return_value=mock_notifier,
            ),
        ):
            resp = client.post("/internal/digest/send", params={"today": today.isoformat()})

        assert resp.status_code == 200
        body = resp.json()
        assert body["delivered"] == 2
        emails = {u["owner_email"] for u in body["users"]}
        assert emails == {"a@example.com", "b-shared@example.com"}
        # Each user's digest carries only their own contacts.
        per_user = {u["owner_id"]: u for u in body["users"]}
        assert per_user[OWNER_A]["count"] == 1
        assert per_user[OWNER_B]["count"] == 1

    @pytest.mark.asyncio
    async def test_failure_for_one_user_does_not_abort_others(self) -> None:
        """When one notifier.send raises, other users still receive their digest."""
        contacts = InMemoryContactRepository()
        users = InMemoryUserRepository()
        await _seed_user(users, user_id=OWNER_A, email="a@example.com")
        await _seed_user(users, user_id=OWNER_B, email="b@example.com")
        client = _build_client(contacts=contacts, users=users)

        # First call raises, second succeeds.
        mock_notifier = AsyncMock()
        mock_notifier.send = AsyncMock(side_effect=[Exception("boom"), "msg"])
        with (
            patch(
                "birthday_tracker.adapters.load_gmail_credentials",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.build_gmail_service",
                return_value=object(),
            ),
            patch(
                "birthday_tracker.adapters.GmailNotifier",
                return_value=mock_notifier,
            ),
        ):
            resp = client.post("/internal/digest/send")

        assert resp.status_code == 200
        body = resp.json()
        assert body["delivered"] == 1
        assert body["failed"] == 1

    @pytest.mark.asyncio
    async def test_oidc_required_when_audience_set(self) -> None:
        """When digest_oidc_audience is set, missing token returns 401."""
        contacts = InMemoryContactRepository()
        client = _build_client(
            contacts=contacts,
            extra_settings={"digest_oidc_audience": "https://example.run.app"},
        )
        resp = client.get("/internal/digest/upcoming", params={"owner_id": OWNER_A})
        assert resp.status_code == 401
