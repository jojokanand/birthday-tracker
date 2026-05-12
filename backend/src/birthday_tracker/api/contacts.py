"""Contacts CRUD router.

Provides the owner-facing REST interface for managing contacts.  All routes
require the caller to be the authenticated owner (stub until issue #7 wires
real auth).

Routes
------
GET    /contacts                 — list all contacts (optional upcoming filter)
POST   /contacts                 — create a new contact
GET    /contacts/{contact_id}    — fetch a single contact
PUT    /contacts/{contact_id}    — replace a contact's editable fields
DELETE /contacts/{contact_id}    — remove a contact
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr, Field, model_validator

from birthday_tracker.api.dependencies import (
    OwnerIdentity,
    get_contact_repository,
    require_owner,
)
from birthday_tracker.api.errors import APIError
from birthday_tracker.models import Contact
from birthday_tracker.models.address import Address
from birthday_tracker.models.birthday import Birthday
from birthday_tracker.services.repositories import ContactRepository

router = APIRouter(prefix="/contacts", tags=["contacts"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateContactBody(BaseModel):
    """Request body for ``POST /contacts``."""

    full_name: str = Field(min_length=1, max_length=200, description="Full name.")
    preferred_name: str | None = Field(
        default=None, max_length=100, description="Nickname used in greetings."
    )
    email: EmailStr | None = Field(default=None, description="Email address.")
    phone: str | None = Field(default=None, description="Phone number (E.164).")
    address: Address | None = Field(default=None, description="Postal address.")
    birthday: Birthday | None = Field(default=None, description="Birthday.")

    @model_validator(mode="after")
    def _require_channel(self) -> CreateContactBody:
        """Ensure at least one of email or phone is supplied.

        Returns:
            ``self`` if valid.

        Raises:
            ValueError: When both ``email`` and ``phone`` are ``None``.
        """
        if self.email is None and self.phone is None:
            raise ValueError("contact must have at least one of email or phone")
        return self


class UpdateContactBody(BaseModel):
    """Request body for ``PUT /contacts/{contact_id}``.

    All fields are optional; only supplied fields are applied.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    preferred_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: Address | None = None
    birthday: Birthday | None = None


class ContactResponse(BaseModel):
    """Wire representation of a :class:`~birthday_tracker.models.Contact`.

    Matches the :class:`Contact` fields but uses ``str`` for UUID/datetime
    so JSON serialization is explicit and stable across Python versions.
    """

    id: UUID
    full_name: str
    preferred_name: str | None
    email: str | None
    phone: str | None
    address: Address | None
    birthday: Birthday | None
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    updated_at: str = Field(description="ISO-8601 UTC last-updated timestamp.")
    days_until_birthday: int | None = Field(
        default=None,
        description="Days until the next occurrence of the contact's birthday, or null.",
    )


# ---------------------------------------------------------------------------
# Birthday helpers
# ---------------------------------------------------------------------------


def _days_until_birthday(birthday: Birthday, today: dt.date | None = None) -> int:
    """Compute calendar days until the next occurrence of ``birthday``.

    Leap-day birthdays (02-29) fall on 03-01 in non-leap years.

    Args:
        birthday: The birthday to evaluate.
        today: Override for the current date (useful in tests).

    Returns:
        Non-negative integer: 0 means today, 1 means tomorrow, etc.
    """
    reference = today or dt.date.today()

    def _bday_in_year(year: int) -> dt.date:
        try:
            return dt.date(year, birthday.month, birthday.day)
        except ValueError:
            return dt.date(year, 3, 1)  # 02-29 → 03-01 in non-leap years

    candidate = _bday_in_year(reference.year)
    if candidate < reference:
        candidate = _bday_in_year(reference.year + 1)
    return (candidate - reference).days


def _build_response(contact: Contact) -> ContactResponse:
    """Convert a :class:`Contact` to :class:`ContactResponse`.

    Args:
        contact: Domain model to convert.

    Returns:
        A :class:`ContactResponse` with ``days_until_birthday`` populated when
        the contact has a birthday set.
    """
    days: int | None = None
    if contact.birthday is not None:
        days = _days_until_birthday(contact.birthday)

    return ContactResponse(
        id=contact.id,
        full_name=contact.full_name,
        preferred_name=contact.preferred_name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        birthday=contact.birthday,
        created_at=contact.created_at.isoformat(),
        updated_at=contact.updated_at.isoformat(),
        days_until_birthday=days,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ContactResponse],
    summary="List all contacts (owner only)",
)
async def list_contacts(
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    _owner: Annotated[OwnerIdentity, Depends(require_owner())],
    upcoming_in_days: Annotated[
        int | None,
        Query(
            ge=0,
            le=365,
            description=(
                "When set, return only contacts whose birthday falls within "
                "the next *N* days (inclusive). Contacts without a birthday "
                "are excluded."
            ),
        ),
    ] = None,
) -> list[ContactResponse]:
    """Return all contacts, optionally filtered to upcoming birthdays.

    Args:
        repo: Injected :class:`ContactRepository`.
        _owner: Authenticated owner identity (stub).
        upcoming_in_days: Optional filter: only contacts with a birthday
            within the next ``upcoming_in_days`` calendar days are returned.
            Contacts without a birthday are omitted when this filter is active.

    Returns:
        List of :class:`ContactResponse` objects, ordered by
        ``days_until_birthday`` when ``upcoming_in_days`` is set, otherwise
        by ascending ``full_name``.
    """
    contacts = await repo.list_all()
    responses = [_build_response(c) for c in contacts]

    if upcoming_in_days is not None:
        responses = [
            r
            for r in responses
            if r.days_until_birthday is not None and r.days_until_birthday <= upcoming_in_days
        ]
        responses.sort(key=lambda r: r.days_until_birthday or 0)
    else:
        responses.sort(key=lambda r: r.full_name.lower())

    return responses


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contact (owner only)",
)
async def create_contact(
    body: CreateContactBody,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    _owner: Annotated[OwnerIdentity, Depends(require_owner())],
) -> ContactResponse:
    """Persist a new contact and return the saved record.

    Args:
        body: Contact creation payload.
        repo: Injected :class:`ContactRepository`.
        _owner: Authenticated owner identity (stub).

    Returns:
        The newly created :class:`ContactResponse`.

    Raises:
        APIError: 422 if the body is invalid (handled by FastAPI before this
            function is called).
    """
    contact = Contact(
        full_name=body.full_name,
        preferred_name=body.preferred_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        birthday=body.birthday,
    )
    await repo.save(contact)
    return _build_response(contact)


@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Fetch a single contact (owner only)",
)
async def get_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    _owner: Annotated[OwnerIdentity, Depends(require_owner())],
) -> ContactResponse:
    """Return the contact with the given ID.

    Args:
        contact_id: UUID of the contact to fetch.
        repo: Injected :class:`ContactRepository`.
        _owner: Authenticated owner identity (stub).

    Returns:
        The :class:`ContactResponse` for the matching contact.

    Raises:
        APIError: 404 if no contact with ``contact_id`` exists.
    """
    contact = await repo.get(contact_id)
    if contact is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Contact not found",
            detail=f"No contact with ID {contact_id}",
        )
    return _build_response(contact)


@router.put(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Update a contact (owner only)",
)
async def update_contact(
    contact_id: UUID,
    body: UpdateContactBody,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    _owner: Annotated[OwnerIdentity, Depends(require_owner())],
) -> ContactResponse:
    """Apply a partial update to an existing contact.

    Only fields explicitly included in ``body`` are changed; omitted fields
    retain their current values.

    Args:
        contact_id: UUID of the contact to update.
        body: Partial update payload.
        repo: Injected :class:`ContactRepository`.
        _owner: Authenticated owner identity (stub).

    Returns:
        The updated :class:`ContactResponse`.

    Raises:
        APIError: 404 if no contact with ``contact_id`` exists.
    """
    contact = await repo.get(contact_id)
    if contact is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Contact not found",
            detail=f"No contact with ID {contact_id}",
        )

    updates = body.model_dump(exclude_unset=True)
    updated = contact.model_copy(update=updates)
    updated.touch()
    await repo.save(updated)
    return _build_response(updated)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a contact (owner only)",
)
async def delete_contact(
    contact_id: UUID,
    repo: Annotated[ContactRepository, Depends(get_contact_repository)],
    _owner: Annotated[OwnerIdentity, Depends(require_owner())],
) -> None:
    """Remove a contact permanently.

    Args:
        contact_id: UUID of the contact to delete.
        repo: Injected :class:`ContactRepository`.
        _owner: Authenticated owner identity (stub).

    Raises:
        APIError: 404 if no contact with ``contact_id`` exists.
    """
    deleted = await repo.delete(contact_id)
    if not deleted:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Contact not found",
            detail=f"No contact with ID {contact_id}",
        )
