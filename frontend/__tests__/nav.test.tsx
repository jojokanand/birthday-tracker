/**
 * Unit tests for the dashboard navigation bar, focused on the new
 * gear-icon dropdown that points at /account.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { Nav } from "@/components/nav";

let mockAuth: { isAuthed: boolean; loading: boolean } = {
  isAuthed: true,
  loading: false,
};
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => mockAuth,
}));

let mockPathname = "/contacts";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

// The sign-out button has its own auth wiring + tests; stub it here so
// this test doesn't have to drag those in.
vi.mock("@/components/sign-out-button", () => ({
  SignOutButton: () => <button>Sign out</button>,
}));

beforeEach(() => {
  mockAuth = { isAuthed: true, loading: false };
  mockPathname = "/contacts";
  cleanup();
});

describe("Nav settings dropdown", () => {
  it("shows a gear button when the user is signed in", () => {
    render(<Nav />);
    expect(
      screen.getByRole("button", { name: /settings/i }),
    ).toBeInTheDocument();
  });

  it("hides the gear button on the sign-in page", () => {
    mockPathname = "/sign-in";
    render(<Nav />);
    expect(
      screen.queryByRole("button", { name: /settings/i }),
    ).not.toBeInTheDocument();
  });

  it("hides the gear button when the user is signed out", () => {
    mockAuth = { isAuthed: false, loading: false };
    render(<Nav />);
    expect(
      screen.queryByRole("button", { name: /settings/i }),
    ).not.toBeInTheDocument();
  });

  it("opens the dropdown and reveals the Account link on click", async () => {
    render(<Nav />);

    // Item lives behind a portal — not in the DOM until the trigger fires.
    expect(screen.queryByRole("menuitem", { name: /account/i })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));

    const item = await waitFor(() =>
      screen.getByRole("menuitem", { name: /account/i }),
    );
    // The Account row is rendered as a Next.js Link so it must carry
    // the href the rest of the app can navigate to.
    const anchor = item.closest("a") ?? item;
    expect(anchor.getAttribute("href")).toBe("/account");
  });
});
