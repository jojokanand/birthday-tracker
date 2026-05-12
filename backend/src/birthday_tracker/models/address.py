"""Postal address value object."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Address(BaseModel):
    """A postal address.

    Validation is intentionally permissive — we accept addresses from any
    country and do not normalize or geocode. The only hard requirements are a
    non-empty first street line and a city; everything else is optional because
    contacts will fill this in via a self-serve form and we do not want to
    block them on, for example, an unfamiliar postal-code format.

    Attributes:
        street1: First line of the street address (e.g. ``"123 Main St"``).
        street2: Optional second line (apartment, suite, etc.).
        city: City or locality name.
        region: State, province, or region. Optional because some countries
            (e.g. Singapore) do not use one.
        postal_code: ZIP / postcode. Optional for the same reason.
        country: ISO 3166-1 alpha-2 country code, uppercased. Defaults to
            ``"US"`` since this is a personal-use app.
    """

    street1: str = Field(min_length=1, max_length=200)
    street2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("country")
    @classmethod
    def _country_uppercase(cls, value: str) -> str:
        """Normalize the ISO country code to uppercase.

        Args:
            value: Raw country code from input.

        Returns:
            The same code uppercased so equality comparisons are stable.
        """
        return value.upper()
