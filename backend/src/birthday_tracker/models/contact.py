"""Contact aggregate model.

A :class:`Contact` is what we store per person in Firestore. The full name and
at least one contact channel (email or phone) are required up front so we can
*reach* them; address and birthday are filled in later via the self-serve form.
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID, uuid4

import phonenumbers
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from birthday_tracker.models.address import Address
from birthday_tracker.models.birthday import Birthday


class Contact(BaseModel):
    """A single person tracked by the app.

    Attributes:
        id: Stable identifier (UUID4) generated server-side at creation.
        full_name: Legal or commonly-used full name.
        preferred_name: Optional shorter / nickname used in greetings.
        email: Verified email address. Optional but at least one of
            ``email`` / ``phone`` must be present.
        phone: E.164-formatted phone number (e.g. ``+14155551234``).
        address: Postal address. Filled in by the contact, not the owner.
        birthday: Birthday. Filled in by the contact, not the owner.
        created_at: Server-set creation timestamp (UTC).
        updated_at: Server-set last-modified timestamp (UTC).
    """

    id: UUID = Field(default_factory=uuid4)
    full_name: str = Field(min_length=1, max_length=200)
    preferred_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = None
    address: Address | None = None
    birthday: Birthday | None = None
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))
    updated_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.UTC))

    @field_validator("phone")
    @classmethod
    def _validate_phone_e164(cls, value: str | None) -> str | None:
        """Validate and normalize the phone number to E.164.

        Args:
            value: Raw phone string. ``None`` passes through unchanged.

        Returns:
            The number reformatted as E.164 (e.g. ``"+14155551234"``).

        Raises:
            ValueError: If the input is not a parseable phone number.
        """
        if value is None:
            return None
        try:
            parsed = phonenumbers.parse(value, "US")
        except phonenumbers.NumberParseException as exc:
            raise ValueError(f"invalid phone number: {value!r}") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"invalid phone number: {value!r}")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    @model_validator(mode="after")
    def _require_contactable_channel(self) -> Contact:
        """Ensure at least one of ``email`` or ``phone`` is present.

        Without one we have no way to send the collection request, so creation
        is blocked at the model layer rather than discovered later in the
        notification adapter.

        Returns:
            ``self`` unchanged when validation passes.

        Raises:
            ValueError: If both channels are ``None``.
        """
        if self.email is None and self.phone is None:
            raise ValueError("contact must have at least one of email or phone")
        return self

    def touch(self) -> None:
        """Bump :attr:`updated_at` to the current UTC time.

        Call from services right before persisting an updated copy.
        """
        self.updated_at = dt.datetime.now(dt.UTC)
