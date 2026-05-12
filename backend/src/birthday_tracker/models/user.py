"""User profile model.

A :class:`User` represents a signed-in owner of the app. The identifier
(``id``) is the Firebase Auth ``uid`` — we do not mint our own. Profile
fields like ``digest_owner_email`` were previously per-process environment
variables; with multi-tenant support each user manages their own settings.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """A signed-in user.

    Attributes:
        id: Stable user identifier — the Firebase Auth ``uid``. Set
            server-side from the authenticated identity on first sign-in.
        email: The email address Firebase Auth verified for this user.
        digest_owner_email: Address the daily birthday digest is sent to.
            Defaults to :attr:`email` on first sign-in but the owner can
            override later (e.g. a shared inbox).
        digest_timezone: IANA timezone name used to determine "today" for
            birthday date math in the daily digest.
        created_at: First-sign-in timestamp (UTC).
        updated_at: Last-modified timestamp (UTC).
    """

    id: str = Field(min_length=1, max_length=128)
    email: EmailStr
    digest_owner_email: EmailStr | None = None
    digest_timezone: str = Field(default="UTC", max_length=64)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))

    @property
    def effective_digest_email(self) -> str:
        """Return the address the daily digest should be sent to.

        Returns:
            :attr:`digest_owner_email` if explicitly set, otherwise
            :attr:`email`.
        """
        return self.digest_owner_email or self.email

    def touch(self) -> None:
        """Bump :attr:`updated_at` to the current UTC time."""
        self.updated_at = dt.datetime.now(dt.UTC)
