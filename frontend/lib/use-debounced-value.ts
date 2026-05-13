/**
 * Tiny debounce hook used by search inputs across the app.
 *
 * @module
 */

"use client";

import * as React from "react";

/**
 * Return ``value`` debounced by ``delayMs`` — useful for search inputs
 * so each keystroke doesn't fire its own request.
 *
 * The first render returns the initial value immediately; only
 * subsequent updates wait for the timer to elapse.
 *
 * @param value Source value to debounce.
 * @param delayMs Debounce window in milliseconds. Defaults to 250 ms.
 * @returns The debounced value, updated after ``delayMs`` of stillness.
 */
export function useDebouncedValue<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const handle = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}
