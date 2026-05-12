"""Unit tests for the contacts CRUD router.

The repository layer is replaced by :class:`InMemoryContactRepository` so
tests never touch Firestore.  They verify HTTP semantics — status codes,
response shapes, sorting, filtering — not business logic.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from birthday_tracker.adapters import InMemoryContactRepository
from birthday_tracker.api.contacts import _days_until_birthday
from birthday_tracker.api.dependencies import get_contact_repository
from birthday_tracker.core.config import AppEnv, Settings
from birthday_tracker.core.config import get_settings as get_settings_dep
from birthday_tracker.main import create_app
from birthday_tracker.models import Contact
from birthday_tracker.models.birthday import Birthday

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_client(repo: InMemoryContactRepository) -> TestClient:
    """Return a :class:`TestClient` with *repo* injected as the contact repository."""
    get_settings_dep.cache_clear()
    app = create_app(settings=Settings(app_env=AppEnv.development, log_level="ERROR"))
    app.dependency_overrides[get_contact_repository] = lambda: repo
    return TestClient(app)


async def _seed(
    repo: InMemoryContactRepository,
    full_name: str = "Test Person",
    email: str | None = "test@example.com",
    preferred_name: str | None = None,
    phone: str | None = None,
    birthday: Birthday | None = None,
) -> Contact:
    """Persist and return a :class:`Contact` with sensible defaults."""
    contact = Contact(
        full_name=full_name,
        email=email,
        preferred_name=preferred_name,
        phone=phone,
        birthday=birthday,
    )
    await repo.save(contact)
    return contact


# ---------------------------------------------------------------------------
# _days_until_birthday unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_days_until_birthday_today() -> None:
    """A birthday that falls on today returns 0."""
    today = dt.date(2025, 6, 15)
    bday = Birthday(month=6, day=15)
    assert _days_until_birthday(bday, today=today) == 0


@pytest.mark.unit
def test_days_until_birthday_tomorrow() -> None:
    """A birthday tomorrow returns 1."""
    today = dt.date(2025, 6, 15)
    bday = Birthday(month=6, day=16)
    assert _days_until_birthday(bday, today=today) == 1


@pytest.mark.unit
def test_days_until_birthday_wraps_to_next_year() -> None:
    """A birthday that already passed this year returns days until next year."""
    today = dt.date(2025, 6, 15)
    bday = Birthday(month=1, day=1)
    result = _days_until_birthday(bday, today=today)
    expected = (dt.date(2026, 1, 1) - today).days
    assert result == expected


@pytest.mark.unit
def test_days_until_birthday_leap_day_non_leap_year() -> None:
    """Feb-29 birthday in a non-leap year maps to Mar-1."""
    today = dt.date(2025, 2, 28)
    bday = Birthday(month=2, day=29)
    result = _days_until_birthday(bday, today=today)
    assert result == 1  # 2025 is not a leap year → birthday maps to Mar-1


# ---------------------------------------------------------------------------
# GET /contacts
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_list_empty_returns_empty_array() -> None:
    """Empty repo → 200 with []."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.get("/contacts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.unit
async def test_list_returns_contacts_sorted_by_name() -> None:
    """Contacts are returned alphabetically by full_name."""
    repo = InMemoryContactRepository()
    await _seed(repo, full_name="Zelda Smith", email="z@example.com")
    await _seed(repo, full_name="Ada Lovelace", email="a@example.com")
    await _seed(repo, full_name="Marco Polo", email="m@example.com")

    client = _build_client(repo)
    resp = client.get("/contacts")

    assert resp.status_code == 200
    names = [c["full_name"] for c in resp.json()]
    assert names == ["Ada Lovelace", "Marco Polo", "Zelda Smith"]


@pytest.mark.unit
async def test_list_response_shape() -> None:
    """Response carries all expected ContactResponse fields."""
    repo = InMemoryContactRepository()
    await _seed(repo, full_name="Ada Lovelace", email="ada@example.com")

    client = _build_client(repo)
    resp = client.get("/contacts")

    assert resp.status_code == 200
    body = resp.json()[0]
    for key in (
        "id",
        "full_name",
        "preferred_name",
        "email",
        "phone",
        "address",
        "birthday",
        "created_at",
        "updated_at",
        "days_until_birthday",
    ):
        assert key in body, f"missing key: {key}"


@pytest.mark.unit
async def test_list_upcoming_filters_by_birthday() -> None:
    """upcoming_in_days=N returns only contacts with birthday within N days."""
    repo = InMemoryContactRepository()
    today = dt.date.today()
    soon = today + dt.timedelta(days=3)
    far = today + dt.timedelta(days=60)

    await _seed(
        repo,
        full_name="Soon Person",
        email="soon@example.com",
        birthday=Birthday(month=soon.month, day=soon.day),
    )
    await _seed(
        repo,
        full_name="Far Person",
        email="far@example.com",
        birthday=Birthday(month=far.month, day=far.day),
    )
    await _seed(repo, full_name="No Birthday", email="none@example.com")

    client = _build_client(repo)
    resp = client.get("/contacts?upcoming_in_days=10")

    assert resp.status_code == 200
    names = [c["full_name"] for c in resp.json()]
    assert "Soon Person" in names
    assert "Far Person" not in names
    assert "No Birthday" not in names


@pytest.mark.unit
async def test_list_upcoming_sorted_by_days() -> None:
    """upcoming_in_days results are ordered nearest-first."""
    repo = InMemoryContactRepository()
    today = dt.date.today()
    day2 = today + dt.timedelta(days=2)
    day5 = today + dt.timedelta(days=5)

    await _seed(
        repo,
        full_name="Day 5",
        email="d5@example.com",
        birthday=Birthday(month=day5.month, day=day5.day),
    )
    await _seed(
        repo,
        full_name="Day 2",
        email="d2@example.com",
        birthday=Birthday(month=day2.month, day=day2.day),
    )

    client = _build_client(repo)
    resp = client.get("/contacts?upcoming_in_days=30")

    names = [c["full_name"] for c in resp.json()]
    assert names.index("Day 2") < names.index("Day 5")


# ---------------------------------------------------------------------------
# POST /contacts
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_create_returns_201() -> None:
    """Valid body → 201 with the created contact."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.post(
        "/contacts",
        json={"full_name": "Ada Lovelace", "email": "ada@example.com"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert "id" in body


@pytest.mark.unit
async def test_create_with_all_fields() -> None:
    """A contact can be created with address and birthday."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.post(
        "/contacts",
        json={
            "full_name": "Ada Lovelace",
            "preferred_name": "Ada",
            "email": "ada@example.com",
            "phone": "+12125551234",
            "address": {
                "street1": "123 Main St",
                "city": "London",
                "country": "GB",
            },
            "birthday": {"month": 12, "day": 10, "year": 1990},
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["preferred_name"] == "Ada"
    assert body["address"]["city"] == "London"
    assert body["birthday"]["month"] == 12


@pytest.mark.unit
def test_create_requires_email_or_phone() -> None:
    """Body without email or phone is rejected (Contact model validates this)."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.post("/contacts", json={"full_name": "No Channel"})

    assert resp.status_code == 422


@pytest.mark.unit
def test_create_returns_422_for_empty_name() -> None:
    """full_name must be non-empty."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.post("/contacts", json={"full_name": "", "email": "x@y.com"})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /contacts/{contact_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_get_returns_200_for_existing() -> None:
    """A known contact ID returns the contact."""
    repo = InMemoryContactRepository()
    contact = await _seed(repo)
    client = _build_client(repo)

    resp = client.get(f"/contacts/{contact.id}")

    assert resp.status_code == 200
    assert resp.json()["id"] == str(contact.id)


@pytest.mark.unit
def test_get_returns_404_for_unknown_id() -> None:
    """An unknown ID returns 404 with problem+json."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.get(f"/contacts/{uuid4()}")

    assert resp.status_code == 404
    assert resp.json()["title"] == "Contact not found"


# ---------------------------------------------------------------------------
# PUT /contacts/{contact_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_update_modifies_fields() -> None:
    """PUT with new fields overwrites them; unset fields are preserved."""
    repo = InMemoryContactRepository()
    contact = await _seed(repo, full_name="Old Name", email="old@example.com")
    client = _build_client(repo)

    resp = client.put(f"/contacts/{contact.id}", json={"full_name": "New Name"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["email"] == "old@example.com"  # unchanged


@pytest.mark.unit
async def test_update_bumps_updated_at() -> None:
    """PUT updates the updated_at timestamp."""
    repo = InMemoryContactRepository()
    contact = await _seed(repo)
    original_updated = contact.updated_at

    client = _build_client(repo)
    resp = client.put(f"/contacts/{contact.id}", json={"preferred_name": "Buddy"})

    assert resp.status_code == 200
    updated_at_str = resp.json()["updated_at"]
    assert updated_at_str != original_updated.isoformat()


@pytest.mark.unit
def test_update_returns_404_for_unknown_id() -> None:
    """PUT on an unknown ID returns 404."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.put(f"/contacts/{uuid4()}", json={"full_name": "Nobody"})

    assert resp.status_code == 404
    assert resp.json()["title"] == "Contact not found"


# ---------------------------------------------------------------------------
# DELETE /contacts/{contact_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_delete_removes_contact() -> None:
    """Deleting an existing contact returns 204 and removes it from the store."""
    repo = InMemoryContactRepository()
    contact = await _seed(repo)
    client = _build_client(repo)

    resp = client.delete(f"/contacts/{contact.id}")
    assert resp.status_code == 204

    # Verify it's gone.
    get_resp = client.get(f"/contacts/{contact.id}")
    assert get_resp.status_code == 404


@pytest.mark.unit
def test_delete_returns_404_for_unknown_id() -> None:
    """DELETE on an unknown ID returns 404."""
    repo = InMemoryContactRepository()
    client = _build_client(repo)

    resp = client.delete(f"/contacts/{uuid4()}")

    assert resp.status_code == 404
    assert resp.json()["title"] == "Contact not found"
