/**
 * Display formatting utilities used across dashboard pages.
 *
 * @module
 */

import type { components } from "./api-types";

/** Convenience alias for the generated Birthday schema. */
export type Birthday = components["schemas"]["Birthday"];

/** Convenience alias for the generated ContactResponse schema. */
export type ContactResponse = components["schemas"]["ContactResponse"];

/**
 * Convert a `days_until_birthday` count into a human-readable label.
 *
 * @param days - Non-negative integer from the API, or `null` if unknown.
 * @returns A short string like `"Today"`, `"Tomorrow"`, `"in 5 days"`, or
 *   `"—"` when `days` is `null`.
 */
export function formatDaysUntilBirthday(days: number | null | undefined): string {
  if (days === null || days === undefined) return "—";
  if (days === 0) return "Today 🎂";
  if (days === 1) return "Tomorrow";
  return `in ${days} days`;
}

/**
 * Format a {@link Birthday} object as `"DD Mon"` (e.g. `"10 Dec"`).
 *
 * @param birthday - Birthday schema object, or `null`.
 * @returns Formatted string, or `"Unknown"` when `birthday` is `null`.
 */
export function formatBirthday(birthday: Birthday | null | undefined): string {
  if (!birthday) return "Unknown";
  const month = new Date(2000, birthday.month - 1, 1).toLocaleString("en", {
    month: "short",
  });
  return `${birthday.day} ${month}${birthday.year ? ` ${birthday.year}` : ""}`;
}

/**
 * Return the greeting name for a contact — preferred name when set, otherwise
 * the first word of `full_name`.
 *
 * @param contact - ContactResponse from the API.
 * @returns A short first-name-style string.
 */
export function greetingName(contact: ContactResponse): string {
  if (contact.preferred_name) return contact.preferred_name;
  return contact.full_name.split(" ")[0];
}
