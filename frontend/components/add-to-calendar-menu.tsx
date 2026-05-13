/**
 * Per-row "Add to calendar" dropdown for the Contacts table.
 *
 * Lists four destinations in priority order:
 *
 * 1. **Google Calendar** — direct deeplink with the `RRULE:FREQ=YEARLY`
 *    in the URL.
 * 2. **Apple Calendar** — downloads the same `.ics` file (Apple is the
 *    default `.ics` handler on macOS / iOS).
 * 3. **Outlook** — same `.ics` (Outlook web's deeplink doesn't carry
 *    recurrence, so the file is the only path that preserves the
 *    yearly RRULE).
 * 4. **Other (.ics)** — same `.ics`, for everything else.
 *
 * The trigger button is only safe to render when the contact has a
 * birthday — the menu doesn't guard against the missing case so the
 * caller (`/contacts` row) does the gating.
 *
 * @module
 */

"use client";

import * as React from "react";
import { CalendarPlus } from "lucide-react";
import { Menu } from "@base-ui/react/menu";
import {
  buildBirthdayIcs,
  buildGoogleCalendarUrl,
  downloadIcs,
  icsFileNameForContact,
} from "@/lib/calendar";
import type { ContactResponse } from "@/lib/format";

/** Props for {@link AddToCalendarMenu}. */
export interface AddToCalendarMenuProps {
  /** Contact whose birthday is being added. Must have ``birthday`` set. */
  contact: ContactResponse;
}

/**
 * Calendar-icon button + dropdown for one contact row.
 *
 * Google opens a new tab to the prefilled "create event" UI; the
 * three `.ics` items kick off a file download with the OS default
 * handler.
 */
export function AddToCalendarMenu({ contact }: AddToCalendarMenuProps) {
  const onGoogle = () => {
    const url = buildGoogleCalendarUrl(contact);
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  };
  const onIcs = () => {
    const content = buildBirthdayIcs(contact);
    if (content) downloadIcs(content, icsFileNameForContact(contact));
  };

  return (
    <Menu.Root>
      <Menu.Trigger
        aria-label={`Add ${contact.full_name}'s birthday to calendar`}
        className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
      >
        <CalendarPlus className="size-4" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={6} align="end">
          <Menu.Popup className="rounded-lg border border-border bg-popover py-1 text-sm shadow-md outline-none min-w-[10rem]">
            <Menu.Item
              onClick={onGoogle}
              className="flex cursor-pointer items-center px-3 py-1.5 hover:bg-muted focus:bg-muted outline-none"
            >
              Google Calendar
            </Menu.Item>
            <Menu.Item
              onClick={onIcs}
              className="flex cursor-pointer items-center px-3 py-1.5 hover:bg-muted focus:bg-muted outline-none"
            >
              Apple Calendar
            </Menu.Item>
            <Menu.Item
              onClick={onIcs}
              className="flex cursor-pointer items-center px-3 py-1.5 hover:bg-muted focus:bg-muted outline-none"
            >
              Outlook
            </Menu.Item>
            <Menu.Item
              onClick={onIcs}
              className="flex cursor-pointer items-center px-3 py-1.5 hover:bg-muted focus:bg-muted outline-none"
            >
              Other (.ics)
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
