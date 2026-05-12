/**
 * Unit tests for `lib/format.ts` formatting utilities.
 */

import { describe, it, expect } from "vitest";
import {
  formatDaysUntilBirthday,
  formatBirthday,
  greetingName,
  type Birthday,
  type ContactResponse,
} from "@/lib/format";

// ---------------------------------------------------------------------------
// formatDaysUntilBirthday
// ---------------------------------------------------------------------------

describe("formatDaysUntilBirthday", () => {
  it('returns "Today 🎂" when days === 0', () => {
    expect(formatDaysUntilBirthday(0)).toBe("Today 🎂");
  });

  it('returns "Tomorrow" when days === 1', () => {
    expect(formatDaysUntilBirthday(1)).toBe("Tomorrow");
  });

  it('returns "in N days" for any value > 1', () => {
    expect(formatDaysUntilBirthday(7)).toBe("in 7 days");
    expect(formatDaysUntilBirthday(30)).toBe("in 30 days");
  });

  it('returns "—" for null', () => {
    expect(formatDaysUntilBirthday(null)).toBe("—");
  });

  it('returns "—" for undefined', () => {
    expect(formatDaysUntilBirthday(undefined)).toBe("—");
  });
});

// ---------------------------------------------------------------------------
// formatBirthday
// ---------------------------------------------------------------------------

describe("formatBirthday", () => {
  it("formats month and day without year", () => {
    const bday: Birthday = { month: 12, day: 10 };
    expect(formatBirthday(bday)).toBe("10 Dec");
  });

  it("includes year when present", () => {
    const bday: Birthday = { month: 3, day: 5, year: 1990 };
    expect(formatBirthday(bday)).toBe("5 Mar 1990");
  });

  it('returns "Unknown" for null', () => {
    expect(formatBirthday(null)).toBe("Unknown");
  });

  it('returns "Unknown" for undefined', () => {
    expect(formatBirthday(undefined)).toBe("Unknown");
  });
});

// ---------------------------------------------------------------------------
// greetingName
// ---------------------------------------------------------------------------

describe("greetingName", () => {
  it("returns preferred_name when set", () => {
    const contact: ContactResponse = {
      id: "a1a2a3a4-b1b2-4c1c-8d1d-e1e2e3e4e5e6",
      full_name: "Ada Lovelace",
      preferred_name: "Ada",
      email: "ada@example.com",
      phone: null,
      address: null,
      birthday: null,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    expect(greetingName(contact)).toBe("Ada");
  });

  it("falls back to first word of full_name when preferred_name is null", () => {
    const contact: ContactResponse = {
      id: "f1f2f3f4-a1a2-4b1b-9c1c-d1d2d3d4d5d6",
      full_name: "Charles Babbage",
      preferred_name: null,
      email: "charles@example.com",
      phone: null,
      address: null,
      birthday: null,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    expect(greetingName(contact)).toBe("Charles");
  });
});
