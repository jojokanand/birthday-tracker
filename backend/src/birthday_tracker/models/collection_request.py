"""Collection request — one outbound ask for a contact's details."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

DEFAULT_TTL = dt.timedelta(days=7)


class Channel(StrEnum):
    """Channel used to deliver a collection request to a contact."""

    sms = "sms"
    email = "email"


class CollectionRequest(BaseModel):
    """One outbound request to a contact for their details.

    The request carries a one-time form token (we store only its hash, never
    the raw token). When the contact submits the form the request is marked
    fulfilled; expired requests are rejected at the form endpoint.

    Attributes:
        id: Stable identifier (UUID4) generated server-side.
        contact_id: The :class:`~birthday_tracker.models.contact.Contact` this
            request is collecting info for.
        channel: Whether the link was sent via SMS or email.
        destination: The phone or email address the link was sent to. Kept on
            the request itself so the audit log is self-contained even if the
            contact later updates their preferred channel.
        token_hash: SHA-256 hex digest of the form token. The raw token never
            leaves the URL embedded in the outbound message.
        created_at: When we issued the request (UTC).
        expires_at: When the form token stops being valid (UTC).
        fulfilled_at: When the contact submitted the form, or ``None`` if
            still pending.
    """

    id: UUID = Field(default_factory=uuid4)
    contact_id: UUID
    channel: Channel
    destination: str = Field(min_length=1, max_length=320)
    token_hash: str = Field(min_length=64, max_length=64)
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    expires_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC) + DEFAULT_TTL)
    fulfilled_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _expires_after_created(self) -> CollectionRequest:
        """Ensure ``expires_at`` is strictly after ``created_at``.

        Returns:
            ``self`` unchanged when validation passes.

        Raises:
            ValueError: If ``expires_at`` is at or before ``created_at``.
        """
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be strictly after created_at")
        return self

    @property
    def is_pending(self) -> bool:
        """Whether the request is still awaiting a submission.

        Returns:
            ``True`` if the form has not been submitted and the token has not
            expired; ``False`` otherwise.
        """
        return self.fulfilled_at is None and dt.datetime.now(dt.UTC) < self.expires_at
