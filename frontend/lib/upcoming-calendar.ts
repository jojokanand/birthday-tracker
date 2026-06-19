/**
 * Date-bucketing helpers for the upcoming-birthdays calendar view.
 *
 * The calendar places each contact on the date of their *next* birthday
 * using the backend-supplied `days_until_birthday` count rather than
 * re-deriving the date from `birthday.month`/`day`. That keeps the grid
 * in lockstep with the rest of the dashboard — including the backend's
 * leap-day rule (29 Feb collapses to 1 Mar in non-leap years) — without
 * duplicating that logic here.
 *
 * Output is a list of week rows (Sunday → Saturday) covering the window
 * `[today, today + windowDays]`, padded out to whole weeks so the grid
 * always renders as a rectangle.
 *
 * @module
 */

import type { ContactResponse } from "@/lib/format";

/** One cell of the calendar grid. */
export interface CalendarDay {
  /** Local-midnight `Date` for this cell. */
  date: Date;
  /** `YYYY-MM-DD` key for this cell (local time, not UTC). */
  iso: string;
  /** Day-of-month, 1–31. */
  dayOfMonth: number;
  /** `true` when the cell falls inside `[today, today + windowDays]`. */
  inWindow: boolean;
  /** `true` when the cell is today. */
  isToday: boolean;
  /** Contacts whose next birthday lands on this date, sorted by name. */
  contacts: ContactResponse[];
}

/**
 * Return a copy of `date` floored to local midnight.
 *
 * @param date - Any `Date`.
 * @returns A new `Date` at 00:00 local time on the same calendar day.
 */
export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/**
 * Add `days` calendar days to `date`, returning a new `Date`.
 *
 * Uses `setDate`, so month/year rollover and DST transitions are handled
 * by the platform date arithmetic.
 *
 * @param date - Starting date.
 * @param days - Number of days to add (may be negative).
 * @returns A new `Date` offset by `days`.
 */
export function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

/**
 * Format a `Date` as a local-time `YYYY-MM-DD` key.
 *
 * Deliberately avoids `toISOString()` (which is UTC) so dates near
 * midnight don't shift across day boundaries depending on the viewer's
 * timezone.
 *
 * @param date - Date to format.
 * @returns The `YYYY-MM-DD` string for the local calendar day.
 */
export function isoDay(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Greeting/sort name for a contact — preferred name, else first word of
 * the full name. Mirrors {@link greetingName} but kept local so the grid
 * builder has no React dependency.
 */
function sortName(contact: ContactResponse): string {
  if (contact.preferred_name) return contact.preferred_name;
  return contact.full_name.split(" ")[0] ?? contact.full_name;
}

/**
 * Build the upcoming-birthdays calendar grid.
 *
 * Contacts are bucketed onto `today + days_until_birthday`; any contact
 * without a `days_until_birthday`, or one falling beyond `windowDays`, is
 * dropped. The returned grid spans whole Sunday→Saturday weeks from the
 * week containing `today` through the week containing `today + windowDays`.
 *
 * @param today - Reference "now"; only its calendar day is used.
 * @param windowDays - Inclusive size of the look-ahead window (e.g. 30).
 * @param contacts - Contacts to place, as returned by `GET /contacts`.
 * @returns Week rows, each a 7-element array of {@link CalendarDay} cells.
 */
export function buildUpcomingCalendar(
  today: Date,
  windowDays: number,
  contacts: ContactResponse[],
): CalendarDay[][] {
  const start = startOfDay(today);
  const todayIso = isoDay(start);

  // Bucket contacts by the ISO day of their next birthday.
  const byDay = new Map<string, ContactResponse[]>();
  for (const contact of contacts) {
    const days = contact.days_until_birthday;
    if (days == null || days < 0 || days > windowDays) continue;
    const key = isoDay(addDays(start, days));
    const bucket = byDay.get(key);
    if (bucket) bucket.push(contact);
    else byDay.set(key, [contact]);
  }
  for (const bucket of byDay.values()) {
    bucket.sort((a, b) =>
      sortName(a).localeCompare(sortName(b), undefined, { sensitivity: "base" }),
    );
  }

  const windowEnd = addDays(start, windowDays);
  // Pad to whole weeks: back up to the Sunday on/before today, run
  // forward to the Saturday on/after the window end.
  const gridStart = addDays(start, -start.getDay());
  const gridEnd = addDays(windowEnd, 6 - windowEnd.getDay());

  const weeks: CalendarDay[][] = [];
  let cursor = gridStart;
  while (cursor <= gridEnd) {
    const week: CalendarDay[] = [];
    for (let i = 0; i < 7; i++) {
      const iso = isoDay(cursor);
      week.push({
        date: cursor,
        iso,
        dayOfMonth: cursor.getDate(),
        inWindow: cursor >= start && cursor <= windowEnd,
        isToday: iso === todayIso,
        contacts: byDay.get(iso) ?? [],
      });
      cursor = addDays(cursor, 1);
    }
    weeks.push(week);
  }
  return weeks;
}
