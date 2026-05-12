"""Unit tests for CollectionRequestService.

Uses the in-memory adapters so tests stay fast and dependency-free.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from birthday_tracker.adapters import (
    InMemoryCollectionRequestRepository,
    InMemoryContactRepository,
)
from birthday_tracker.core.tokens import TokenExpired, TokenInvalid, sign_token
from birthday_tracker.models import Address, Birthday, Channel, Contact
from birthday_tracker.services.collection_requests import (
    CollectionRequestService,
    ContactNotFound,
    FormSubmission,
    RequestNotPending,
)

SECRET = "unit-test-secret"


def _service(
    *,
    contacts: InMemoryContactRepository | None = None,
    requests: InMemoryCollectionRequestRepository | None = None,
    ttl: int = 60,
) -> CollectionRequestService:
    return CollectionRequestService(
        contacts=contacts or InMemoryContactRepository(),
        requests=requests or InMemoryCollectionRequestRepository(),
        token_secret=SECRET,
        token_ttl_seconds=ttl,
        public_base_url="https://example.test/",
    )


def _submission() -> FormSubmission:
    return FormSubmission(
        full_name="Ada Lovelace",
        preferred_name="Ada",
        address=Address(street1="1 Main", city="London", country="GB"),
        birthday=Birthday(month=12, day=10, year=1990),
    )


@pytest.mark.unit
async def test_constructor_rejects_blank_secret() -> None:
    with pytest.raises(ValueError, match="token_secret must be non-empty"):
        CollectionRequestService(
            contacts=InMemoryContactRepository(),
            requests=InMemoryCollectionRequestRepository(),
            token_secret="",
            token_ttl_seconds=60,
            public_base_url="x",
        )


@pytest.mark.unit
async def test_constructor_rejects_non_positive_ttl() -> None:
    with pytest.raises(ValueError, match="token_ttl_seconds must be positive"):
        CollectionRequestService(
            contacts=InMemoryContactRepository(),
            requests=InMemoryCollectionRequestRepository(),
            token_secret=SECRET,
            token_ttl_seconds=0,
            public_base_url="x",
        )


@pytest.mark.unit
async def test_issue_persists_request_and_returns_url() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests)

    issued = await svc.issue(
        contact_id=contact.id,
        channel=Channel.email,
        destination="ada@example.com",
    )

    assert issued.url.startswith("https://example.test/form/")
    assert issued.url.endswith(issued.token)
    assert issued.request.contact_id == contact.id
    persisted = await requests.get(issued.request.id)
    assert persisted is not None
    assert persisted.token_hash == issued.request.token_hash


@pytest.mark.unit
async def test_issue_strips_trailing_slash_from_base_url() -> None:
    contacts = InMemoryContactRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts)

    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )
    assert "//form/" not in issued.url


@pytest.mark.unit
async def test_issue_raises_when_contact_missing() -> None:
    svc = _service()
    with pytest.raises(ContactNotFound):
        await svc.issue(contact_id=uuid4(), channel=Channel.email, destination="x@y.com")


@pytest.mark.unit
async def test_lookup_returns_pending_request() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests)
    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )

    request = await svc.lookup(issued.token)
    assert request.id == issued.request.id


@pytest.mark.unit
async def test_lookup_raises_token_invalid_for_unknown_token() -> None:
    svc = _service()
    foreign_token = sign_token(request_id=uuid4(), ttl_seconds=60, secret=SECRET)
    with pytest.raises(TokenInvalid, match="unknown token"):
        await svc.lookup(foreign_token)


@pytest.mark.unit
async def test_lookup_raises_token_expired() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests, ttl=1)
    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )
    import time

    time.sleep(1.1)
    with pytest.raises(TokenExpired):
        await svc.lookup(issued.token)


@pytest.mark.unit
async def test_lookup_raises_when_request_already_fulfilled() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests)
    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )

    await svc.fulfill(token=issued.token, submission=_submission())
    with pytest.raises(RequestNotPending):
        await svc.lookup(issued.token)


@pytest.mark.unit
async def test_fulfill_updates_contact_and_marks_request_fulfilled() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="placeholder", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests)
    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )

    updated = await svc.fulfill(token=issued.token, submission=_submission())
    assert updated.full_name == "Ada Lovelace"
    assert updated.preferred_name == "Ada"
    assert updated.birthday is not None and updated.birthday.year == 1990
    fresh_contact = await contacts.get(contact.id)
    assert fresh_contact is not None and fresh_contact.full_name == "Ada Lovelace"
    persisted = await requests.get(issued.request.id)
    assert persisted is not None and persisted.fulfilled_at is not None


@pytest.mark.unit
async def test_fulfill_raises_when_contact_deleted_after_issue() -> None:
    contacts = InMemoryContactRepository()
    requests = InMemoryCollectionRequestRepository()
    contact = Contact(full_name="Ada", email="ada@example.com")
    await contacts.save(contact)
    svc = _service(contacts=contacts, requests=requests)
    issued = await svc.issue(
        contact_id=contact.id, channel=Channel.email, destination="ada@example.com"
    )

    await contacts.delete(contact.id)
    with pytest.raises(ContactNotFound):
        await svc.fulfill(token=issued.token, submission=_submission())
