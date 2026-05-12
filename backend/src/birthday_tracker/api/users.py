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
    """Wire representation of :class:`~birthday_tracker.models.User`."""

    id: str
    email: str
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


def _to_response(user: User) -> UserProfileResponse:
    """Convert a :class:`User` to its wire representation.

    Args:
        user: The persisted profile.

    Returns:
        A :class:`UserProfileResponse`.
    """
    return UserProfileResponse(
        id=user.id,
        email=user.email,
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
    return _to_response(user)


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
    return _to_response(updated)
