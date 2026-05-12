"""Unit tests for :class:`InMemoryContactRepository`.

Exercises the contract every :class:`ContactRepository` must satisfy.
"""

from __future__ import annotations

import pytest

from birthday_tracker.adapters import InMemoryContactRepository
from tests._contracts import contact_repository as contract


@pytest.fixture
def repo() -> InMemoryContactRepository:
    """Build a fresh empty in-memory repository for each test."""
    return InMemoryContactRepository()


@pytest.mark.unit
async def test_get_missing(repo: InMemoryContactRepository) -> None:
    await contract.assert_get_returns_none_for_missing(repo)


@pytest.mark.unit
async def test_save_and_get(repo: InMemoryContactRepository) -> None:
    await contract.assert_save_and_get_roundtrip(repo)


@pytest.mark.unit
async def test_save_replaces(repo: InMemoryContactRepository) -> None:
    await contract.assert_save_replaces_existing(repo)


@pytest.mark.unit
async def test_delete_existing(repo: InMemoryContactRepository) -> None:
    await contract.assert_delete_existing_returns_true(repo)


@pytest.mark.unit
async def test_delete_missing(repo: InMemoryContactRepository) -> None:
    await contract.assert_delete_missing_returns_false(repo)


@pytest.mark.unit
async def test_list_for_owner_empty(repo: InMemoryContactRepository) -> None:
    await contract.assert_list_for_owner_empty(repo)


@pytest.mark.unit
async def test_list_for_owner_returns_inserted(repo: InMemoryContactRepository) -> None:
    await contract.assert_list_for_owner_returns_inserted(repo)


@pytest.mark.unit
async def test_mutation_isolation(repo: InMemoryContactRepository) -> None:
    await contract.assert_mutation_does_not_leak_into_store(repo)


# ----- Cross-tenant isolation -------------------------------------------


@pytest.mark.unit
async def test_get_filters_by_owner(repo: InMemoryContactRepository) -> None:
    await contract.assert_get_filters_by_owner(repo)


@pytest.mark.unit
async def test_delete_filters_by_owner(repo: InMemoryContactRepository) -> None:
    await contract.assert_delete_filters_by_owner(repo)


@pytest.mark.unit
async def test_list_for_owner_isolates_tenants(repo: InMemoryContactRepository) -> None:
    await contract.assert_list_for_owner_isolates_tenants(repo)


@pytest.mark.unit
async def test_duplicate_details_across_tenants(repo: InMemoryContactRepository) -> None:
    await contract.assert_duplicate_details_across_tenants_allowed(repo)
