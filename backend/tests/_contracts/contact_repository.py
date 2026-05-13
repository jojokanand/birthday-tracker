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


# ----- list_page / count_for_owner contract -----------------------------


def _seedable(full_name: str, *, email: str | None, preferred: str | None = None) -> Contact:
    """Build a contact for paging/search tests.

    Default phone is ``None`` (caller supplies email) so the ``email``
    parameter is meaningful — passing ``None`` exercises the
    phone-only branch.
    """
    return Contact(
        owner_id=OWNER,
        full_name=full_name,
        preferred_name=preferred,
        email=email,
        phone=None if email else "+14155551234",
    )


async def assert_list_page_orders_by_full_name_lower(repo: ContactRepository) -> None:
    """The page is ordered case-insensitively by ``full_name``.

    Specifically, "ada" sorts before "Bob" — lowercasing means the
    capitalisation of the source field doesn't influence position.
    """
    await repo.save(_seedable("Bob Smith", email="b@example.com"))
    await repo.save(_seedable("ada Lovelace", email="a@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10)
    assert [c.full_name for c in items] == ["ada Lovelace", "Bob Smith"]


async def assert_list_page_walks_via_cursor(repo: ContactRepository) -> None:
    """Cursor pagination visits every contact exactly once."""
    for i in range(15):
        await repo.save(_seedable(f"User {i:02d}", email=f"u{i:02d}@example.com"))

    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        items, cursor = await repo.list_page(OWNER, limit=10, cursor=cursor)
        seen.extend(c.full_name for c in items)
        pages += 1
        if cursor is None:
            break
    assert pages == 2  # 10 + 5
    assert sorted(seen) == [f"User {i:02d}" for i in range(15)]


async def assert_count_for_owner_returns_total(repo: ContactRepository) -> None:
    """``count_for_owner`` matches the number of inserted contacts."""
    assert await repo.count_for_owner(OWNER) == 0
    for i in range(7):
        await repo.save(_seedable(f"User {i}", email=f"u{i}@example.com"))
    assert await repo.count_for_owner(OWNER) == 7


async def assert_q_prefix_matches_full_name(repo: ContactRepository) -> None:
    """``q`` is a case-insensitive prefix on ``full_name``."""
    await repo.save(_seedable("Ada Lovelace", email="ada@example.com"))
    await repo.save(_seedable("Bob Smith", email="bob@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10, q="ad")
    assert [c.full_name for c in items] == ["Ada Lovelace"]
    assert await repo.count_for_owner(OWNER, q="ad") == 1


async def assert_q_prefix_matches_preferred_name(repo: ContactRepository) -> None:
    """``q`` matches preferred_name as well as full_name."""
    await repo.save(_seedable("Augusta King", email="aking@example.com", preferred="Ada"))
    await repo.save(_seedable("Bob Smith", email="bob@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10, q="ada")
    assert [c.full_name for c in items] == ["Augusta King"]


async def assert_q_prefix_matches_email(repo: ContactRepository) -> None:
    """``q`` matches the email prefix too."""
    await repo.save(_seedable("Marco Polo", email="ada@example.com"))
    await repo.save(_seedable("Bob Smith", email="bob@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10, q="ada@")
    assert [c.full_name for c in items] == ["Marco Polo"]


async def assert_q_dedupes_overlapping_matches(repo: ContactRepository) -> None:
    """A contact whose name and email both match returns once."""
    await repo.save(_seedable("Ada Lovelace", email="ada@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10, q="ada")
    assert len(items) == 1
    assert await repo.count_for_owner(OWNER, q="ada") == 1


async def assert_q_whitespace_only_is_no_filter(repo: ContactRepository) -> None:
    """A whitespace-only ``q`` is treated as no filter."""
    await repo.save(_seedable("Ada Lovelace", email="ada@example.com"))
    await repo.save(_seedable("Bob Smith", email="bob@example.com"))

    items, _ = await repo.list_page(OWNER, limit=10, q="   ")
    assert {c.full_name for c in items} == {"Ada Lovelace", "Bob Smith"}


async def assert_unknown_cursor_yields_empty_page(repo: ContactRepository) -> None:
    """A cursor that doesn't exist in the filtered set returns an empty page."""
    await repo.save(_seedable("Ada Lovelace", email="ada@example.com"))

    items, next_cursor = await repo.list_page(OWNER, limit=10, cursor=str(uuid4()))
    assert items == []
    assert next_cursor is None


async def assert_list_page_isolates_tenants(repo: ContactRepository) -> None:
    """Pagination respects the owner_id filter."""
    mine = _seedable("Mine Person", email="mine@example.com")
    theirs = Contact(
        owner_id=OTHER_OWNER,
        full_name="Theirs Person",
        email="theirs@example.com",
    )
    await repo.save(mine)
    await repo.save(theirs)

    items, _ = await repo.list_page(OWNER, limit=10)
    assert [c.full_name for c in items] == ["Mine Person"]
    assert await repo.count_for_owner(OWNER) == 1
    assert await repo.count_for_owner(OTHER_OWNER) == 1
