/**
 * Component tests for {@link AddToCalendarMenu}.
 *
 * The menu lives behind a base-ui Portal, so `screen.getByRole`
 * queries against `document.body` find the items once the trigger
 * has been clicked.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { AddToCalendarMenu } from "@/components/add-to-calendar-menu";
import type { ContactResponse } from "@/lib/format";

const CONTACT: ContactResponse = {
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

beforeEach(() => {
  cleanup();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AddToCalendarMenu", () => {
  it("renders a calendar trigger with an accessible label", () => {
    render(<AddToCalendarMenu contact={CONTACT} />);
    expect(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    ).toBeInTheDocument();
  });

  it("lists Google first, then Apple / Outlook / Other when the menu opens", async () => {
    render(<AddToCalendarMenu contact={CONTACT} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );

    const items = await waitFor(() => {
      const found = screen.getAllByRole("menuitem");
      if (found.length < 4) throw new Error("menu items not mounted yet");
      return found;
    });

    expect(items.map((el) => el.textContent)).toEqual([
      "Google Calendar",
      "Apple Calendar",
      "Outlook",
      "Other (.ics)",
    ]);
  });

  it("opens a new tab to the Google Calendar URL when Google is selected", async () => {
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    render(<AddToCalendarMenu contact={CONTACT} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );
    const item = await waitFor(() =>
      screen.getByRole("menuitem", { name: /google calendar/i }),
    );
    fireEvent.click(item);

    expect(openSpy).toHaveBeenCalledTimes(1);
    const [url, target] = openSpy.mock.calls[0];
    expect(url).toContain("calendar.google.com/calendar/render");
    expect(url).toContain("RRULE%3AFREQ%3DYEARLY");
    expect(target).toBe("_blank");
  });

  it("triggers an .ics download when Apple Calendar is selected", async () => {
    // jsdom's URL.createObjectURL is undefined by default — stub it.
    const createObjectURL = vi.fn().mockReturnValue("blob://fake");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: revokeObjectURL,
      configurable: true,
    });

    // Spy on the anchor click so the test can assert the download
    // intent without jsdom actually navigating.
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click");

    render(<AddToCalendarMenu contact={CONTACT} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );
    const item = await waitFor(() =>
      screen.getByRole("menuitem", { name: /^apple calendar$/i }),
    );
    fireEvent.click(item);

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchorClick).toHaveBeenCalledTimes(1);
  });

  it("Google item is a no-op on a contact with no birthday", async () => {
    // The contacts page already gates the button on ``contact.birthday``,
    // but the inner ``if (url)`` guard keeps caller misuse from
    // calling ``window.open(null, …)``. Cover the false branch.
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    render(<AddToCalendarMenu contact={{ ...CONTACT, birthday: null }} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );
    fireEvent.click(
      await waitFor(() =>
        screen.getByRole("menuitem", { name: /google calendar/i }),
      ),
    );

    expect(openSpy).not.toHaveBeenCalled();
  });

  it("ICS item is a no-op on a contact with no birthday", async () => {
    Object.defineProperty(URL, "createObjectURL", {
      value: vi.fn().mockReturnValue("blob://fake"),
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click");

    render(<AddToCalendarMenu contact={{ ...CONTACT, birthday: null }} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );
    fireEvent.click(
      await waitFor(() =>
        screen.getByRole("menuitem", { name: /^apple calendar$/i }),
      ),
    );

    // The inner ``if (content)`` guard short-circuits before the
    // download trick fires.
    expect(anchorClick).not.toHaveBeenCalled();
  });

  it("uses the same .ics path for the Outlook item", async () => {
    const createObjectURL = vi.fn().mockReturnValue("blob://fake");
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click");

    render(<AddToCalendarMenu contact={CONTACT} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: /add ada lovelace's birthday to calendar/i,
      }),
    );
    fireEvent.click(
      await waitFor(() => screen.getByRole("menuitem", { name: /^outlook$/i })),
    );

    expect(anchorClick).toHaveBeenCalledTimes(1);
  });
});
