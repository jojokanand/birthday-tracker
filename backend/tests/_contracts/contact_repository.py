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


def make_contact(email: str = "ada@example.com", preferred: str | None = "Ada") -> Contact:
    """Build a fully-populated :class:`Contact` for tests.

    Args:
        email: Email address to use. Defaults to a generic value; pass a
            unique string when a single test needs multiple contacts.
        preferred: Preferred name. Pass ``None`` to omit it.

    Returns:
        A :class:`Contact` with every optional field set, suitable for
        round-trip serialization tests.
    """
    return Contact(
        full_name="Ada Lovelace",
        preferred_name=preferred,
        email=email,
        phone="+14155551234",
        address=Address(street1="1 Main", city="London", country="GB"),
        birthday=Birthday(month=12, day=10, year=1990),
    )


async def assert_get_returns_none_for_missing(repo: ContactRepository) -> None:
    """:meth:`ContactRepository.get` must return ``None`` for unknown IDs."""
    assert await repo.get(uuid4()) is None


async def assert_save_and_get_roundtrip(repo: ContactRepository) -> None:
    """A saved contact must be readable back, fully equal to the original."""
    contact = make_contact()
    await repo.save(contact)
    fetched = await repo.get(contact.id)
    assert fetched == contact


async def assert_save_replaces_existing(repo: ContactRepository) -> None:
    """Saving the same ID twice must overwrite the prior value."""
    contact = make_contact()
    await repo.save(contact)

    updated = contact.model_copy(update={"preferred_name": "Augusta"})
    await repo.save(updated)

    fetched = await repo.get(contact.id)
    assert fetched is not None
    assert fetched.preferred_name == "Augusta"


async def assert_delete_existing_returns_true(repo: ContactRepository) -> None:
    """Deleting a present contact returns ``True`` and removes it."""
    contact = make_contact()
    await repo.save(contact)
    assert await repo.delete(contact.id) is True
    assert await repo.get(contact.id) is None


async def assert_delete_missing_returns_false(repo: ContactRepository) -> None:
    """Deleting an unknown contact returns ``False`` and is otherwise a no-op."""
    assert await repo.delete(uuid4()) is False


async def assert_list_all_empty(repo: ContactRepository) -> None:
    """A fresh repository lists no contacts."""
    assert await repo.list_all() == []


async def assert_list_all_returns_inserted(repo: ContactRepository) -> None:
    """Inserted contacts appear in ``list_all`` (order-independent)."""
    a = make_contact(email="a@example.com")
    b = make_contact(email="b@example.com")
    await repo.save(a)
    await repo.save(b)

    contacts = await repo.list_all()
    assert {c.id for c in contacts} == {a.id, b.id}


async def assert_mutation_does_not_leak_into_store(repo: ContactRepository) -> None:
    """Mutating the object returned by ``get`` must not affect the store.

    Real DB adapters always serialize through the wire, so callers cannot
    accidentally mutate stored state. The in-memory fake mimics this via
    deep copies — this contract test guards both implementations.
    """
    contact = make_contact()
    await repo.save(contact)

    fetched = await repo.get(contact.id)
    assert fetched is not None
    fetched.preferred_name = "MUTATED"

    refetched = await repo.get(contact.id)
    assert refetched is not None
    assert refetched.preferred_name == "Ada"
