/**
 * Month-grid rendering of upcoming birthdays.
 *
 * Presentational only: the caller supplies the already-bucketed week
 * rows from {@link buildUpcomingCalendar}. Cells outside the look-ahead
 * window are dimmed, today is ringed, and each birthday is rendered as a
 * badge showing the contact's greeting name.
 *
 * @module
 */

"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { greetingName } from "@/lib/format";
import type { CalendarDay } from "@/lib/upcoming-calendar";

/** Sunday-first weekday column headers. */
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

/** Short month label (e.g. `"Jul"`) for a date. */
function monthLabel(date: Date): string {
  return date.toLocaleString("en", { month: "short" });
}

/**
 * Render the upcoming-birthdays calendar grid.
 *
 * @param props.weeks - Week rows from {@link buildUpcomingCalendar}.
 */
export function UpcomingCalendar({ weeks }: { weeks: CalendarDay[][] }) {
  return (
    <div data-testid="upcoming-calendar" className="overflow-x-auto">
      <div className="grid grid-cols-7 gap-px rounded-lg border bg-border min-w-[640px]">
        {WEEKDAYS.map((label) => (
          <div
            key={label}
            className="bg-muted/50 px-2 py-1.5 text-center text-xs font-medium text-muted-foreground"
          >
            {label}
          </div>
        ))}
        {weeks.flat().map((cell) => (
          <div
            key={cell.iso}
            data-testid={`calendar-cell-${cell.iso}`}
            data-in-window={cell.inWindow}
            className={[
              "min-h-24 bg-background p-1.5 flex flex-col gap-1",
              cell.inWindow ? "" : "bg-muted/30 text-muted-foreground/50",
            ].join(" ")}
          >
            <div className="flex items-baseline justify-between">
              <span
                className={[
                  "text-xs tabular-nums",
                  cell.isToday
                    ? "flex size-5 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground"
                    : "text-muted-foreground",
                ].join(" ")}
              >
                {cell.dayOfMonth}
              </span>
              {cell.dayOfMonth === 1 && (
                <span className="text-[10px] font-medium uppercase text-muted-foreground">
                  {monthLabel(cell.date)}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-1">
              {cell.contacts.map((contact) => (
                <Badge
                  key={contact.id}
                  variant={cell.isToday ? "default" : "secondary"}
                  className="w-full justify-start truncate"
                  title={contact.full_name}
                >
                  {cell.isToday ? "🎂 " : ""}
                  {greetingName(contact)}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
