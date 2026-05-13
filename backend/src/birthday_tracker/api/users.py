"""Owner-side router for the caller's own user profile.

A user profile (:class:`~birthday_tracker.models.User`) holds per-tenant
settings — currently the daily digest's destination email and timezone.
The frontend calls ``GET /me`` on app load; the first call creates the
profile from the Firebase ID-token claims, and subsequent calls return
the stored row.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field

from birthday_tracker.api.dependencies import get_user_repository, require_user
from birthday_tracker.core.auth import Identity
from birthday_tracker.models import User
from birthday_tracker.services.repositories import UserRepository

router = APIRouter(prefix="/me", tags=["users"])


class UserProfileResponse(BaseModel):
    """Wire representation of :class:`~birthday_tracker.models.User`.

    Identity-derived fields (``first_name``, ``last_name``, ``phone``)
    come straight from the verified Firebase token on every request —
    they are not persisted in the User document, so editing them is a
    Firebase / Google account concern, not an app concern. Persisted
    fields (``digest_*``) live on the User row and can be updated via
    ``PUT /me``.
    """

    id: str
    email: str
    first_name: str | None = Field(
        description="Owner's first name, derived from the Firebase display name."
    )
    last_name: str | None = Field(
        description="Owner's last name (joined remainder of the display name)."
    )
    phone: str | None = Field(
        description="Phone number from the Firebase token, or ``None`` when unset."
    )
    digest_owner_email: str | None
    digest_timezone: str
    created_at: str
    updated_at: str


class UpdateProfileBody(BaseModel):
    """Request body for ``PUT /me`` — both fields optional."""

    digest_owner_email: EmailStr | None = Field(
        default=None,
        description="Where the daily digest should be delivered. Defaults to the sign-in email.",
    )
    digest_timezone: str | None = Field(
        default=None,
        max_length=64,
        description="IANA timezone name used for digest date math.",
    )


def _split_display_name(display_name: str | None) -> tuple[str | None, str | None]:
    """Split a Firebase display name into first / last components.

    The first whitespace-separated token is the first name; everything
    after is joined back together for the last name. Single-token names
    yield ``(token, None)``. Empty / whitespace-only input yields
    ``(None, None)``.

    Args:
        display_name: Raw Firebase ``name`` claim, or ``None``.

    Returns:
        ``(first_name, last_name)`` tuple of optional strings.
    """
    if not display_name or not display_name.strip():
        return (None, None)
    tokens = display_name.strip().split()
    first = tokens[0]
    last = " ".join(tokens[1:]) if len(tokens) > 1 else None
    return (first, last)


def _to_response(user: User, identity: Identity) -> UserProfileResponse:
    """Convert a :class:`User` to its wire representation.

    Args:
        user: The persisted profile (digest_* fields, timestamps).
        identity: Authenticated caller — supplies the identity-derived
            fields (first name, last name, phone) on every request.

    Returns:
        A :class:`UserProfileResponse`.
    """
    first_name, last_name = _split_display_name(identity.display_name)
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        first_name=first_name,
        last_name=last_name,
        phone=identity.phone_number,
        digest_owner_email=user.digest_owner_email,
        digest_timezone=user.digest_timezone,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=UserProfileResponse,
    summary="Get (or create) the caller's profile",
)
async def get_or_create_profile(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
    identity: Annotated[Identity, Depends(require_user)],
) -> UserProfileResponse:
    """Return the caller's profile, creating it on first sign-in.

    Args:
        repo: Injected :class:`UserRepository`.
        identity: Authenticated caller — supplies the ``uid`` and verified
            email.

    Returns:
        The :class:`UserProfileResponse` for the caller's profile.
    """
    user = await repo.get(identity.user_id)
    if user is None:
        user = User(id=identity.user_id, email=identity.email)
        await repo.save(user)
    return _to_response(user, identity)


@router.put(
    "",
    response_model=UserProfileResponse,
    summary="Update the caller's profile",
    status_code=status.HTTP_200_OK,
)
async def update_profile(
    body: UpdateProfileBody,
    repo: Annotated[UserRepository, Depends(get_user_repository)],
    identity: Annotated[Identity, Depends(require_user)],
) -> UserProfileResponse:
    """Apply a partial update to the caller's profile.

    Args:
        body: Partial update — only fields explicitly provided are applied.
        repo: Injected :class:`UserRepository`.
        identity: Authenticated caller.

    Returns:
        The updated :class:`UserProfileResponse`.
    """
    user = await repo.get(identity.user_id)
    if user is None:
        # Treat update-before-first-read as upsert from the auth claims.
        user = User(id=identity.user_id, email=identity.email)

    updates = body.model_dump(exclude_unset=True)
    updated = user.model_copy(update=updates)
    updated.updated_at = dt.datetime.now(dt.UTC)
    await repo.save(updated)
    return _to_response(updated, identity)
