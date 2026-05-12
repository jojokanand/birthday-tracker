"""Contract assertions every :class:`ContactRepository` implementation must satisfy.

Concrete test files (one per implementation) supply a ``repo`` fixture and call
these helper functions. This keeps the unit and integration suites genuinely
identical in behavior — if either drifts, the bug is in the implementation,
not the tests.
"""

from __future__ import annotations

from uuid import uuid4

from birthday_tracker.models import Address, Birthday, Contact
from birthday_tracker.services import ContactRepository

OWNER = "test-owner"
OTHER_OWNER = "other-owner"


def make_contact(
    email: str = "ada@example.com",
    preferred: str | None = "Ada",
    owner_id: str = OWNER,
) -> Contact:
    """Build a fully-populated :class:`Contact` for tests.

    Args:
        email: Email address to use. Defaults to a generic value; pass a
            unique string when a single test needs multiple contacts.
        preferred: Preferred name. Pass ``None`` to omit it.
        owner_id: Owner ``uid`` for the contact. Defaults to the shared
            test owner so single-tenant tests don't need to specify it;
            tenant-isolation tests pass a different value.

    Returns:
        A :class:`Contact` with every optional field set, suitable for
        round-trip serialization tests.
    """
    return Contact(
        owner_id=owner_id,
        full_name="Ada Lovelace",
        preferred_name=preferred,
        email=email,
        phone="+14155551234",
        address=Address(street1="1 Main", city="London", country="GB"),
        birthday=Birthday(month=12, day=10, year=1990),
    )


async def assert_get_returns_none_for_missing(repo: ContactRepository) -> None:
    """:meth:`ContactRepository.get` must return ``None`` for unknown IDs."""
    assert await repo.get(uuid4(), OWNER) is None


async def assert_save_and_get_roundtrip(repo: ContactRepository) -> None:
    """A saved contact must be readable back, fully equal to the original."""
    contact = make_contact()
    await repo.save(contact)
    fetched = await repo.get(contact.id, OWNER)
    assert fetched == contact


async def assert_save_replaces_existing(repo: ContactRepository) -> None:
    """Saving the same ID twice must overwrite the prior value."""
    contact = make_contact()
    await repo.save(contact)

    updated = contact.model_copy(update={"preferred_name": "Augusta"})
    await repo.save(updated)

    fetched = await repo.get(contact.id, OWNER)
    assert fetched is not None
    assert fetched.preferred_name == "Augusta"


async def assert_delete_existing_returns_true(repo: ContactRepository) -> None:
    """Deleting a present contact returns ``True`` and removes it."""
    contact = make_contact()
    await repo.save(contact)
    assert await repo.delete(contact.id, OWNER) is True
    assert await repo.get(contact.id, OWNER) is None


async def assert_delete_missing_returns_false(repo: ContactRepository) -> None:
    """Deleting an unknown contact returns ``False`` and is otherwise a no-op."""
    assert await repo.delete(uuid4(), OWNER) is False


async def assert_list_for_owner_empty(repo: ContactRepository) -> None:
    """A fresh repository lists no contacts for any owner."""
    assert await repo.list_for_owner(OWNER) == []


async def assert_list_for_owner_returns_inserted(repo: ContactRepository) -> None:
    """Inserted contacts appear in ``list_for_owner`` (order-independent)."""
    a = make_contact(email="a@example.com")
    b = make_contact(email="b@example.com")
    await repo.save(a)
    await repo.save(b)

    contacts = await repo.list_for_owner(OWNER)
    assert {c.id for c in contacts} == {a.id, b.id}


async def assert_mutation_does_not_leak_into_store(repo: ContactRepository) -> None:
    """Mutating the object returned by ``get`` must not affect the store.

    Real DB adapters always serialize through the wire, so callers cannot
    accidentally mutate stored state. The in-memory fake mimics this via
    deep copies — this contract test guards both implementations.
    """
    contact = make_contact()
    await repo.save(contact)

    fetched = await repo.get(contact.id, OWNER)
    assert fetched is not None
    fetched.preferred_name = "MUTATED"

    refetched = await repo.get(contact.id, OWNER)
    assert refetched is not None
    assert refetched.preferred_name == "Ada"


# ----- Cross-tenant isolation contract -----------------------------------


async def assert_get_filters_by_owner(repo: ContactRepository) -> None:
    """Fetching a contact owned by someone else must return ``None``."""
    contact = make_contact()
    await repo.save(contact)
    assert await repo.get(contact.id, OTHER_OWNER) is None


async def assert_delete_filters_by_owner(repo: ContactRepository) -> None:
    """Deleting a contact owned by someone else must be a no-op."""
    contact = make_contact()
    await repo.save(contact)

    assert await repo.delete(contact.id, OTHER_OWNER) is False
    # And the contact is still there for its real owner:
    assert await repo.get(contact.id, OWNER) is not None


async def assert_list_for_owner_isolates_tenants(repo: ContactRepository) -> None:
    """list_for_owner returns only the requested owner's rows."""
    mine = make_contact(email="mine@example.com", owner_id=OWNER)
    theirs = make_contact(email="theirs@example.com", owner_id=OTHER_OWNER)
    await repo.save(mine)
    await repo.save(theirs)

    assert {c.id for c in await repo.list_for_owner(OWNER)} == {mine.id}
    assert {c.id for c in await repo.list_for_owner(OTHER_OWNER)} == {theirs.id}


async def assert_duplicate_details_across_tenants_allowed(repo: ContactRepository) -> None:
    """Two users may store contacts with identical fields without conflict."""
    mine = make_contact(owner_id=OWNER)
    twin = make_contact(owner_id=OTHER_OWNER)  # same details, different owner
    await repo.save(mine)
    await repo.save(twin)

    assert (await repo.get(mine.id, OWNER)) is not None
    assert (await repo.get(twin.id, OTHER_OWNER)) is not None
    assert mine.id != twin.id  # IDs are random UUIDs; details collide, IDs don't
