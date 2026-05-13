/**
 * Unit tests for the /account page.
 *
 * The API client + Next navigation are mocked so the test focuses on
 * the field-rendering logic and the `—` fallbacks.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import AccountPage from "@/app/account/page";

const mockApiClient = { GET: vi.fn() };
const mockGet = mockApiClient.GET;
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => mockApiClient,
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthed: true, loading: false }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

function envelope(fields: {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
}) {
  return {
    data: {
      id: "uid-1",
      email: fields.email ?? null,
      first_name: fields.first_name ?? null,
      last_name: fields.last_name ?? null,
      phone: fields.phone ?? null,
      digest_owner_email: null,
      digest_timezone: "UTC",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    error: undefined,
    response: { status: 200 },
  };
}

beforeEach(() => {
  vi.resetAllMocks();
  cleanup();
});

describe("AccountPage", () => {
  it("shows the heading and a loading line on first paint", () => {
    // Never-resolving promise so the page stays in the loading branch.
    mockGet.mockReturnValueOnce(new Promise(() => {}));
    render(<AccountPage />);
    expect(
      screen.getByRole("heading", { name: /account/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/loading…/i)).toBeInTheDocument();
  });

  it("renders all four fields from a populated response", async () => {
    mockGet.mockResolvedValueOnce(
      envelope({
        first_name: "Jyothsna",
        last_name: "Kanand",
        email: "jyothsnapk17@gmail.com",
        phone: "+14155551234",
      }),
    );

    render(<AccountPage />);

    await waitFor(() => expect(screen.getByText("Jyothsna")).toBeInTheDocument());
    expect(screen.getByText("Kanand")).toBeInTheDocument();
    expect(screen.getByText("jyothsnapk17@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("+14155551234")).toBeInTheDocument();
  });

  it("renders a muted '—' for missing fields", async () => {
    mockGet.mockResolvedValueOnce(
      envelope({
        first_name: "Cher",
        last_name: null,
        email: "cher@example.com",
        phone: null,
      }),
    );

    render(<AccountPage />);

    await waitFor(() => expect(screen.getByText("Cher")).toBeInTheDocument());
    // Two missing fields → two em-dash fallbacks.
    const dashes = screen.getAllByText("—");
    expect(dashes).toHaveLength(2);
  });

  it("renders dashes for every field on an API error", async () => {
    mockGet.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "boom" },
      response: { status: 500 },
    });

    render(<AccountPage />);

    await waitFor(() => expect(screen.queryByText(/loading…/i)).not.toBeInTheDocument());
    // All four fields fall back to "—".
    expect(screen.getAllByText("—")).toHaveLength(4);
  });
});
