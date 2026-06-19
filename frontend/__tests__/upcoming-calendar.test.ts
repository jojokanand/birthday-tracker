/**
 * Unit tests for `lib/upcoming-calendar.ts` date-bucketing helpers.
 *
 * Dates are constructed with the local-time `Date(y, m, d)` constructor
 * (matching the helpers) so assertions don't drift with the runner's
 * timezone.
 */

import { describe, it, expect } from "vitest";
import {
  addDays,
  buildUpcomingCalendar,
  isoDay,
  startOfDay,
  type CalendarDay,
} from "@/lib/upcoming-calendar";
import type { ContactResponse } from "@/lib/format";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Build a minimal contact placed `daysUntil` days out. */
function contact(
  id: string,
  daysUntil: number | null,
  overrides: Partial<ContactResponse> = {},
): ContactResponse {
  return {
    id,
    full_name: id,
    preferred_name: null,
    email: null,
    phone: null,
    address: null,
    birthday: { month: 6, day: 15, year: null },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    days_until_birthday: daysUntil,
    ...overrides,
  };
}

/** Flatten the grid to the single cell matching `iso`, or `undefined`. */
function cellFor(weeks: CalendarDay[][], iso: string): CalendarDay | undefined {
  return weeks.flat().find((c) => c.iso === iso);
}

// ---------------------------------------------------------------------------
// startOfDay / addDays / isoDay
// ---------------------------------------------------------------------------

describe("startOfDay", () => {
  it("floors the time to local midnight", () => {
    const d = startOfDay(new Date(2026, 5, 18, 13, 45, 30));
    expect(d.getHours()).toBe(0);
    expect(d.getMinutes()).toBe(0);
    expect(isoDay(d)).toBe("2026-06-18");
  });
});

describe("addDays", () => {
  it("rolls over month boundaries", () => {
    expect(isoDay(addDays(new Date(2026, 5, 28), 5))).toBe("2026-07-03");
  });

  it("handles negative offsets", () => {
    expect(isoDay(addDays(new Date(2026, 0, 1), -1))).toBe("2025-12-31");
  });
});

describe("isoDay", () => {
  it("zero-pads month and day", () => {
    expect(isoDay(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});

// ---------------------------------------------------------------------------
// buildUpcomingCalendar
// ---------------------------------------------------------------------------

describe("buildUpcomingCalendar", () => {
  // A Thursday, so today.getDay() === 4.
  const today = new Date(2026, 5, 18);

  it("returns whole Sunday→Saturday weeks covering the window", () => {
    const weeks = buildUpcomingCalendar(today, 30, []);
    for (const week of weeks) {
      expect(week).toHaveLength(7);
    }
    // First cell is the Sunday on/before today (14 Jun 2026).
    expect(weeks[0][0].iso).toBe("2026-06-14");
    expect(weeks[0][0].date.getDay()).toBe(0);
    // Last cell is a Saturday on/after today+30 (18 Jul 2026 → 18 Jul
    // is a Saturday, so the grid ends there).
    const last = weeks[weeks.length - 1][6];
    expect(last.date.getDay()).toBe(6);
    expect(last.date >= addDays(startOfDay(today), 30)).toBe(true);
  });

  it("places a contact on today + days_until_birthday", () => {
    const weeks = buildUpcomingCalendar(today, 30, [contact("a", 5)]);
    const cell = cellFor(weeks, "2026-06-23"); // 18 Jun + 5
    expect(cell?.contacts.map((c) => c.id)).toEqual(["a"]);
  });

  it("places a 0-day contact on today and flags the cell", () => {
    const weeks = buildUpcomingCalendar(today, 30, [contact("a", 0)]);
    const cell = cellFor(weeks, "2026-06-18");
    expect(cell?.isToday).toBe(true);
    expect(cell?.contacts.map((c) => c.id)).toEqual(["a"]);
  });

  it("drops contacts with no birthday, negative, or out-of-window days", () => {
    const weeks = buildUpcomingCalendar(today, 30, [
      contact("none", null),
      contact("past", -1),
      contact("far", 31),
    ]);
    expect(weeks.flat().every((c) => c.contacts.length === 0)).toBe(true);
  });

  it("includes the contact exactly on the window edge", () => {
    const weeks = buildUpcomingCalendar(today, 30, [contact("edge", 30)]);
    const cell = cellFor(weeks, isoDay(addDays(startOfDay(today), 30)));
    expect(cell?.inWindow).toBe(true);
    expect(cell?.contacts.map((c) => c.id)).toEqual(["edge"]);
  });

  it("marks pre-today and post-window padding cells as out of window", () => {
    // A Friday, so today+30 (19 Jul) is a Sunday — the grid pads out to
    // the following Saturday, giving trailing in-grid padding cells.
    const friday = new Date(2026, 5, 19);
    const weeks = buildUpcomingCalendar(friday, 30, []);
    expect(cellFor(weeks, "2026-06-18")?.inWindow).toBe(false); // yesterday
    expect(cellFor(weeks, "2026-06-19")?.inWindow).toBe(true); // today
    expect(cellFor(weeks, "2026-07-19")?.inWindow).toBe(true); // window edge
    const dayAfterWindow = isoDay(addDays(startOfDay(friday), 31));
    expect(cellFor(weeks, dayAfterWindow)?.inWindow).toBe(false); // 20 Jul
  });

  it("groups multiple contacts on one day, sorted by greeting name", () => {
    const weeks = buildUpcomingCalendar(today, 30, [
      contact("z", 3, { full_name: "Zoe Z" }),
      contact("a", 3, { preferred_name: "Ada", full_name: "Adelaide A" }),
    ]);
    const cell = cellFor(weeks, "2026-06-21");
    expect(cell?.contacts.map((c) => c.id)).toEqual(["a", "z"]);
  });

  it("handles a window that straddles a month boundary", () => {
    const monthEnd = new Date(2026, 5, 25); // 25 Jun
    const weeks = buildUpcomingCalendar(monthEnd, 30, [contact("july", 10)]);
    const cell = cellFor(weeks, "2026-07-05"); // 25 Jun + 10
    expect(cell?.contacts.map((c) => c.id)).toEqual(["july"]);
    expect(cell?.inWindow).toBe(true);
  });
});
