/**
 * Unit tests for the calendar-event helpers.
 *
 * Pure-function exports — no DOM / network mocks needed.
 */

import { describe, it, expect } from "vitest";
import {
  addDays,
  buildBirthdayIcs,
  buildGoogleCalendarUrl,
  eventDateForBirthday,
  eventTitleForContact,
  firstNameForContact,
  formatDateBasic,
  icsFileNameForContact,
  isLeapYear,
} from "@/lib/calendar";
import type { ContactResponse } from "@/lib/format";

const BASE_CONTACT: ContactResponse = {
  id: "11111111-2222-3333-4444-555555555555",
  full_name: "Ada Lovelace",
  preferred_name: "Ada",
  email: "ada@example.com",
  phone: null,
  address: null,
  birthday: { month: 12, day: 10, year: 1990 },
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

describe("isLeapYear", () => {
  it.each([
    [2000, true],
    [2020, true],
    [2024, true],
    [1900, false],
    [2025, false],
    [2100, false],
  ])("year %s → %s", (year, expected) => {
    expect(isLeapYear(year)).toBe(expected);
  });
});

describe("eventDateForBirthday", () => {
  it("uses the contact's month/day for ordinary dates", () => {
    expect(eventDateForBirthday({ month: 12, day: 10 }, 2025)).toEqual({
      year: 2025,
      month: 12,
      day: 10,
    });
  });

  it("keeps Feb 29 in a leap year", () => {
    expect(eventDateForBirthday({ month: 2, day: 29 }, 2024)).toEqual({
      year: 2024,
      month: 2,
      day: 29,
    });
  });

  it("maps Feb 29 to Mar 1 in a non-leap year", () => {
    expect(eventDateForBirthday({ month: 2, day: 29 }, 2025)).toEqual({
      year: 2025,
      month: 3,
      day: 1,
    });
  });
});

describe("formatDateBasic / addDays", () => {
  it("zero-pads month and day", () => {
    expect(formatDateBasic({ year: 2025, month: 3, day: 7 })).toBe("20250307");
  });

  it("advances across month boundaries", () => {
    expect(addDays({ year: 2025, month: 2, day: 28 }, 1)).toEqual({
      year: 2025,
      month: 3,
      day: 1,
    });
  });

  it("advances across year boundaries", () => {
    expect(addDays({ year: 2025, month: 12, day: 31 }, 1)).toEqual({
      year: 2026,
      month: 1,
      day: 1,
    });
  });
});

describe("firstNameForContact", () => {
  it("prefers preferred_name", () => {
    expect(firstNameForContact(BASE_CONTACT)).toBe("Ada");
  });

  it("falls back to the first token of full_name", () => {
    expect(
      firstNameForContact({ ...BASE_CONTACT, preferred_name: null }),
    ).toBe("Ada");
  });

  it("falls back to 'Contact' when both are unusable", () => {
    expect(
      firstNameForContact({
        ...BASE_CONTACT,
        preferred_name: null,
        full_name: "   ",
      }),
    ).toBe("Contact");
  });
});

describe("eventTitleForContact / icsFileNameForContact", () => {
  it("uses the first name in the event title", () => {
    expect(eventTitleForContact(BASE_CONTACT)).toBe("Ada's birthday");
  });

  it("kebab-cases the filename", () => {
    expect(icsFileNameForContact(BASE_CONTACT)).toBe("ada-birthday.ics");
  });

  it("falls back to a 'contact' slug when the name strips to nothing", () => {
    // ``full_name`` is non-nullable in ContactResponse, so the only
    // way to reach the static fallback is through firstNameForContact's
    // own "Contact" → slug "contact" path. Verify both routes:
    expect(
      icsFileNameForContact({
        ...BASE_CONTACT,
        preferred_name: null,
        full_name: "   X",
      }).startsWith("x-birthday"),
    ).toBe(true);
    // Emoji-only first name strips down to empty after the slug regex,
    // triggering the ``|| "contact"`` fallback inside the filename
    // builder.
    expect(
      icsFileNameForContact({
        ...BASE_CONTACT,
        preferred_name: "🎂",
      }),
    ).toBe("contact-birthday.ics");
  });
});

describe("buildGoogleCalendarUrl", () => {
  it("returns null when the contact has no birthday", () => {
    const url = buildGoogleCalendarUrl({ ...BASE_CONTACT, birthday: null });
    expect(url).toBeNull();
  });

  it("renders an all-day yearly-recurring template URL anchored at the current year", () => {
    const url = buildGoogleCalendarUrl(BASE_CONTACT, new Date("2025-06-01T12:00:00Z"));
    expect(url).not.toBeNull();
    const parsed = new URL(url!);
    expect(parsed.origin + parsed.pathname).toBe(
      "https://calendar.google.com/calendar/render",
    );
    expect(parsed.searchParams.get("action")).toBe("TEMPLATE");
    expect(parsed.searchParams.get("text")).toBe("Ada's birthday");
    expect(parsed.searchParams.get("dates")).toBe("20251210/20251211");
    expect(parsed.searchParams.get("recur")).toBe("RRULE:FREQ=YEARLY");
  });

  it("maps Feb 29 birthdays to Mar 1 in non-leap years", () => {
    const url = buildGoogleCalendarUrl(
      { ...BASE_CONTACT, birthday: { month: 2, day: 29, year: null } },
      new Date("2025-01-01T12:00:00Z"),
    );
    const parsed = new URL(url!);
    expect(parsed.searchParams.get("dates")).toBe("20250301/20250302");
  });
});

describe("buildBirthdayIcs", () => {
  it("returns null when the contact has no birthday", () => {
    expect(buildBirthdayIcs({ ...BASE_CONTACT, birthday: null })).toBeNull();
  });

  it("emits a VEVENT with all-day DTSTART and yearly RRULE", () => {
    const ics = buildBirthdayIcs(BASE_CONTACT, new Date("2025-06-01T15:30:00Z"));
    expect(ics).not.toBeNull();
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain(`UID:birthday-${BASE_CONTACT.id}@birthday-tracker`);
    expect(ics).toContain("DTSTAMP:20250601T153000Z");
    expect(ics).toContain("DTSTART;VALUE=DATE:20251210");
    expect(ics).toContain("SUMMARY:Ada's birthday");
    expect(ics).toContain("RRULE:FREQ=YEARLY");
    expect(ics).toContain("END:VEVENT");
    expect(ics).toContain("END:VCALENDAR");
  });

  it("uses CRLF line endings (RFC 5545)", () => {
    const ics = buildBirthdayIcs(BASE_CONTACT, new Date("2025-06-01T15:30:00Z"));
    expect(ics).toContain("\r\n");
    // …and the trailing line ends in CRLF too (Apple Calendar is picky).
    expect(ics!.endsWith("\r\n")).toBe(true);
  });

  it("maps Feb 29 birthdays to Mar 1 in non-leap years", () => {
    const ics = buildBirthdayIcs(
      { ...BASE_CONTACT, birthday: { month: 2, day: 29, year: null } },
      new Date("2025-01-01T12:00:00Z"),
    );
    expect(ics).toContain("DTSTART;VALUE=DATE:20250301");
  });

  it("keeps Feb 29 in a leap year", () => {
    const ics = buildBirthdayIcs(
      { ...BASE_CONTACT, birthday: { month: 2, day: 29, year: null } },
      new Date("2024-01-01T12:00:00Z"),
    );
    expect(ics).toContain("DTSTART;VALUE=DATE:20240229");
  });
});
