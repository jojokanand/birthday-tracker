"""Integration tests for :class:`FirestoreContactRepository`.

Runs the same contract that :mod:`tests.unit.adapters.test_in_memory` runs
against the in-memory fake — if behavior diverges, one of the implementations
has a bug.
"""

from __future__ import annotations

import pytest

from birthday_tracker.adapters import FirestoreContactRepository
from tests._contracts import contact_repository as contract


@pytest.mark.integration
async def test_get_missing(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_get_returns_none_for_missing(firestore_repo)


@pytest.mark.integration
async def test_save_and_get(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_save_and_get_roundtrip(firestore_repo)


@pytest.mark.integration
async def test_save_replaces(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_save_replaces_existing(firestore_repo)


@pytest.mark.integration
async def test_delete_existing(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_delete_existing_returns_true(firestore_repo)


@pytest.mark.integration
async def test_delete_missing(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_delete_missing_returns_false(firestore_repo)


@pytest.mark.integration
async def test_list_for_owner_empty(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_list_for_owner_empty(firestore_repo)


@pytest.mark.integration
async def test_list_for_owner_returns_inserted(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_list_for_owner_returns_inserted(firestore_repo)


@pytest.mark.integration
async def test_mutation_isolation(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_mutation_does_not_leak_into_store(firestore_repo)


# ----- Cross-tenant isolation -------------------------------------------


@pytest.mark.integration
async def test_get_filters_by_owner(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_get_filters_by_owner(firestore_repo)


@pytest.mark.integration
async def test_delete_filters_by_owner(firestore_repo: FirestoreContactRepository) -> None:
    await contract.assert_delete_filters_by_owner(firestore_repo)


@pytest.mark.integration
async def test_list_for_owner_isolates_tenants(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_list_for_owner_isolates_tenants(firestore_repo)


@pytest.mark.integration
async def test_duplicate_details_across_tenants(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_duplicate_details_across_tenants_allowed(firestore_repo)


# ----- list_page / count_for_owner --------------------------------------


@pytest.mark.integration
async def test_list_page_orders_by_full_name_lower(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_list_page_orders_by_full_name_lower(firestore_repo)


@pytest.mark.integration
async def test_list_page_walks_via_cursor(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_list_page_walks_via_cursor(firestore_repo)


@pytest.mark.integration
async def test_count_for_owner_returns_total(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_count_for_owner_returns_total(firestore_repo)


@pytest.mark.integration
async def test_q_prefix_matches_full_name(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_q_prefix_matches_full_name(firestore_repo)


@pytest.mark.integration
async def test_q_prefix_matches_preferred_name(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_q_prefix_matches_preferred_name(firestore_repo)


@pytest.mark.integration
async def test_q_prefix_matches_email(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_q_prefix_matches_email(firestore_repo)


@pytest.mark.integration
async def test_q_dedupes_overlapping_matches(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_q_dedupes_overlapping_matches(firestore_repo)


@pytest.mark.integration
async def test_q_whitespace_only_is_no_filter(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_q_whitespace_only_is_no_filter(firestore_repo)


@pytest.mark.integration
async def test_unknown_cursor_yields_empty_page(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_unknown_cursor_yields_empty_page(firestore_repo)


@pytest.mark.integration
async def test_list_page_isolates_tenants(
    firestore_repo: FirestoreContactRepository,
) -> None:
    await contract.assert_list_page_isolates_tenants(firestore_repo)
