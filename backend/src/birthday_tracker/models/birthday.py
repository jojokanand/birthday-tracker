"""Birthday value object.

Stored as month/day plus an optional year. Some contacts share month/day only
(e.g. for privacy or because the year is unknown), so the year is nullable.
The model rejects impossible month/day combinations such as ``02-30``.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator


class Birthday(BaseModel):
    """Month, day, and optional year of a person's birthday.

    Attributes:
        month: Calendar month, 1 (January) through 12 (December).
        day: Day of the month, 1 through 31. Validated against ``month``
            (and ``year`` when present) so impossible dates are rejected.
        year: Four-digit Gregorian year, or ``None`` if unknown / withheld.
            Constrained to a sensible human range (1900–current year).
    """

    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    year: int | None = Field(default=None, ge=1900)

    @model_validator(mode="after")
    def _validate_real_date(self) -> Birthday:
        """Reject month/day combinations that do not exist (e.g. ``02-30``).

        When ``year`` is supplied we use it; otherwise we use a known leap year
        (2000) so that ``02-29`` without a year is still accepted.

        Returns:
            ``self`` unchanged if the date is real.

        Raises:
            ValueError: If the month/day (and optional year) cannot be
                constructed as a real :class:`datetime.date`.
        """
        probe_year = self.year or 2000  # 2000 is a leap year — allows 02-29
        try:
            dt.date(probe_year, self.month, self.day)
        except ValueError as exc:
            raise ValueError(f"invalid birthday: {self.month:02d}-{self.day:02d}") from exc

        if self.year is not None and self.year > dt.date.today().year:
            raise ValueError(f"birthday year {self.year} is in the future")
        return self
