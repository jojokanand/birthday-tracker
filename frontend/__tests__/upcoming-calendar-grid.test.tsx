/**
 * Unit tests for the `<UpcomingCalendar>` presentational grid component.
 *
 * Week rows are produced by {@link buildUpcomingCalendar} from a fixed
 * "today" so the rendered cells are deterministic regardless of when the
 * suite runs.
 */

import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { UpcomingCalendar } from "@/components/upcoming-calendar";
import { buildUpcomingCalendar } from "@/lib/upcoming-calendar";
import type { ContactResponse } from "@/lib/format";

const TODAY = new Date(2026, 5, 18); // Thu 18 Jun 2026

function contact(
  id: string,
  daysUntil: number,
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

afterEach(cleanup);

describe("UpcomingCalendar", () => {
  it("renders the seven weekday column headers", () => {
    render(<UpcomingCalendar weeks={buildUpcomingCalendar(TODAY, 30, [])} />);
    for (const label of ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders a badge with the greeting name on the birthday's cell", () => {
    const weeks = buildUpcomingCalendar(TODAY, 30, [
      contact("a", 5, { preferred_name: "Ada", full_name: "Adelaide Lovelace" }),
    ]);
    render(<UpcomingCalendar weeks={weeks} />);

    const cell = screen.getByTestId("calendar-cell-2026-06-23"); // 18 Jun + 5
    expect(within(cell).getByText("Ada")).toBeInTheDocument();
    // Full name is exposed via the badge's title attribute.
    expect(within(cell).getByTitle("Adelaide Lovelace")).toBeInTheDocument();
  });

  it("prefixes today's birthdays with a cake and dims out-of-window days", () => {
    const weeks = buildUpcomingCalendar(TODAY, 30, [contact("born-today", 0)]);
    render(<UpcomingCalendar weeks={weeks} />);

    const todayCell = screen.getByTestId("calendar-cell-2026-06-18");
    expect(todayCell.dataset.inWindow).toBe("true");
    expect(within(todayCell).getByText(/🎂/)).toBeInTheDocument();

    // The Sunday padding cell before today sits outside the window.
    const padCell = screen.getByTestId("calendar-cell-2026-06-14");
    expect(padCell.dataset.inWindow).toBe("false");
  });

  it("labels the first of a month inside the grid", () => {
    const weeks = buildUpcomingCalendar(TODAY, 30, []);
    render(<UpcomingCalendar weeks={weeks} />);
    const firstOfJuly = screen.getByTestId("calendar-cell-2026-07-01");
    expect(within(firstOfJuly).getByText(/jul/i)).toBeInTheDocument();
  });
});
