/**
 * Calendar-event helpers for the "Add to calendar" dropdown.
 *
 * Two outputs, one shared shape:
 *
 * - {@link buildGoogleCalendarUrl} — a `calendar.google.com/calendar/render`
 *   deeplink that prefills the event in the Google Calendar UI.
 * - {@link buildBirthdayIcs} — an RFC-5545 VEVENT inside a VCALENDAR
 *   suitable for Apple Calendar / Outlook / Yahoo / Fastmail and
 *   anyone else that consumes `.ics`.
 *
 * Both produce an all-day event titled `"{first name}'s birthday"`
 * that recurs yearly forever (`RRULE:FREQ=YEARLY` with no `UNTIL` /
 * `COUNT`). The first occurrence sits in the current calendar year so
 * the event shows up on the user's calendar immediately.
 *
 * @module
 */

import type { ContactResponse } from "@/lib/format";

/** Date the all-day event should start on. */
export interface EventDate {
  year: number;
  /** Calendar month, 1–12. */
  month: number;
  /** Day of month, 1–31. */
  day: number;
}

/**
 * Return ``true`` when the given Gregorian ``year`` is a leap year.
 */
export function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

/**
 * Resolve a contact's birthday to a concrete date in the given year.
 *
 * Leap-day birthdays in a non-leap year collapse to **Mar 1** —
 * mirrors the backend's `_days_until_birthday` mapping so the
 * dashboard and the calendar agree on "this year's birthday".
 *
 * @param birthday Month/day (year ignored).
 * @param year Calendar year to anchor the first occurrence at.
 * @returns The adjusted `(year, month, day)` triple.
 */
export function eventDateForBirthday(
  birthday: { month: number; day: number },
  year: number,
): EventDate {
  if (birthday.month === 2 && birthday.day === 29 && !isLeapYear(year)) {
    return { year, month: 3, day: 1 };
  }
  return { year, month: birthday.month, day: birthday.day };
}

/** Two-digit zero-padded helper for ICS / Google date strings. */
function pad2(value: number): string {
  return value.toString().padStart(2, "0");
}

/**
 * Format a date as `YYYYMMDD` — used by both the Google URL and the
 * ICS `DTSTART;VALUE=DATE` field.
 */
export function formatDateBasic(date: EventDate): string {
  return `${date.year}${pad2(date.month)}${pad2(date.day)}`;
}

/**
 * Add ``days`` calendar days to ``date``, returning a new
 * {@link EventDate}. Used to compute the all-day end date Google
 * wants (start/end exclusive).
 */
export function addDays(date: EventDate, days: number): EventDate {
  // ``Date.UTC`` to avoid local-timezone DST shifts.
  const ms = Date.UTC(date.year, date.month - 1, date.day) + days * 86_400_000;
  const next = new Date(ms);
  return {
    year: next.getUTCFullYear(),
    month: next.getUTCMonth() + 1,
    day: next.getUTCDate(),
  };
}

/**
 * Best guess at the contact's first name for the event title.
 *
 * `preferred_name` wins when set, then the first whitespace token of
 * `full_name`, then the literal `Contact` fallback.
 */
export function firstNameForContact(contact: ContactResponse): string {
  const fromPreferred = (contact.preferred_name ?? "").trim().split(/\s+/)[0];
  if (fromPreferred) return fromPreferred;
  // ``full_name`` is non-nullable in ContactResponse — no ``?? ""`` needed.
  const fromFull = contact.full_name.trim().split(/\s+/)[0];
  if (fromFull) return fromFull;
  return "Contact";
}

/** Title shown in the calendar event — `"{first}'s birthday"`. */
export function eventTitleForContact(contact: ContactResponse): string {
  return `${firstNameForContact(contact)}'s birthday`;
}

/** Filename suggested when the user downloads the ICS file. */
export function icsFileNameForContact(contact: ContactResponse): string {
  const slug = firstNameForContact(contact)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${slug || "contact"}-birthday.ics`;
}

/**
 * Build the `calendar.google.com/calendar/render` URL that prefills
 * a Google Calendar "create event" UI.
 *
 * Returns `null` when the contact has no birthday — the UI gates the
 * button on this case but defensive nulls keep the helper safe to
 * call unconditionally in tests.
 *
 * @param contact The contact whose birthday to schedule.
 * @param now Override for "right now" — only used in tests.
 */
export function buildGoogleCalendarUrl(
  contact: ContactResponse,
  now: Date = new Date(),
): string | null {
  if (!contact.birthday) return null;
  const start = eventDateForBirthday(contact.birthday, now.getFullYear());
  // Google's all-day deeplink takes ``YYYYMMDD/YYYYMMDD`` with the
  // end date exclusive, i.e. one day after the start.
  const end = addDays(start, 1);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: eventTitleForContact(contact),
    dates: `${formatDateBasic(start)}/${formatDateBasic(end)}`,
    recur: "RRULE:FREQ=YEARLY",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

/**
 * Build the body of an `.ics` file carrying the same yearly birthday
 * event as {@link buildGoogleCalendarUrl}.
 *
 * The `UID` is stable per contact so re-importing the same file
 * updates the existing event in standards-compliant clients rather
 * than creating duplicates.
 *
 * Returns `null` when the contact has no birthday.
 *
 * @param contact The contact whose birthday to schedule.
 * @param now Override for "right now" — only used in tests.
 */
export function buildBirthdayIcs(
  contact: ContactResponse,
  now: Date = new Date(),
): string | null {
  if (!contact.birthday) return null;
  const start = eventDateForBirthday(contact.birthday, now.getFullYear());
  const dtStamp =
    `${now.getUTCFullYear()}${pad2(now.getUTCMonth() + 1)}${pad2(now.getUTCDate())}` +
    `T${pad2(now.getUTCHours())}${pad2(now.getUTCMinutes())}${pad2(now.getUTCSeconds())}Z`;
  // RFC 5545 mandates CRLF line endings.
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Birthday Tracker//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:birthday-${contact.id}@birthday-tracker`,
    `DTSTAMP:${dtStamp}`,
    `DTSTART;VALUE=DATE:${formatDateBasic(start)}`,
    `SUMMARY:${eventTitleForContact(contact)}`,
    "RRULE:FREQ=YEARLY",
    "TRANSP:TRANSPARENT",
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ];
  return lines.join("\r\n");
}

/**
 * Trigger a download of ``content`` as ``filename`` from the browser.
 *
 * Uses the throw-away `<a download>` + `URL.createObjectURL` trick so
 * the user's calendar app picks the file up via the OS default
 * handler.
 */
export function downloadIcs(content: string, filename: string): void {
  const blob = new Blob([content], { type: "text/calendar;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Let the browser kick off the download before we release the URL.
  setTimeout(() => URL.revokeObjectURL(href), 0);
}
