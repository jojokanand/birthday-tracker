/**
 * Unit tests for the {@link IssueRequestForm} component.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { IssueRequestForm } from "@/components/issue-request-form";
import type { ContactResponse } from "@/lib/format";

// ---------------------------------------------------------------------------
// Mock the API client
// ---------------------------------------------------------------------------

vi.mock("@/lib/api", () => ({
  apiClient: {
    POST: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api";

const mockPost = apiClient.POST as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

// Proper RFC 4122 v4 UUIDs (version=4, variant=8/9/a/b in 3rd nibble of 4th group).
const ADA_ID = "a1a2a3a4-b1b2-4c1c-8d1d-e1e2e3e4e5e6";
const CHARLES_ID = "f1f2f3f4-a1a2-4b1b-9c1c-d1d2d3d4d5d6";

const CONTACTS: ContactResponse[] = [
  {
    id: ADA_ID,
    full_name: "Ada Lovelace",
    preferred_name: "Ada",
    email: "ada@example.com",
    phone: null,
    address: null,
    birthday: null,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: CHARLES_ID,
    full_name: "Charles Babbage",
    preferred_name: null,
    email: null,
    phone: "+12125551234",
    address: null,
    birthday: null,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Select Ada, pick email channel, fill destination, then click submit. */
async function fillAndSubmit(container: HTMLElement) {
  // Change the native select value directly (react-hook-form reads DOM at submit).
  const contactSelect = container.querySelector<HTMLSelectElement>("#contact_id")!;
  fireEvent.change(contactSelect, { target: { value: ADA_ID } });

  // Pick email channel.
  const emailRadio = screen.getByDisplayValue("email");
  fireEvent.click(emailRadio);

  // Fill in destination.
  const destInput = container.querySelector<HTMLInputElement>("#destination")!;
  fireEvent.change(destInput, { target: { value: "ada@example.com" } });

  // Submit.
  fireEvent.click(screen.getByRole("button", { name: /generate form link/i }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("IssueRequestForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders contact names in the selector", () => {
    render(<IssueRequestForm contacts={CONTACTS} />);
    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
    expect(screen.getByText(/Charles Babbage/)).toBeInTheDocument();
  });

  it("displays the form URL after successful submission", async () => {
    const FORM_URL = "https://example.com/form/abc.def";
    mockPost.mockResolvedValue({
      data: {
        request_id: "req-1",
        contact_id: ADA_ID,
        channel: "email",
        destination: "ada@example.com",
        expires_at: "2030-01-01T00:00:00Z",
        form_url: FORM_URL,
      },
      error: undefined,
      response: { status: 201 },
    });

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    await fillAndSubmit(container);

    await waitFor(() => {
      expect(screen.getByText(FORM_URL)).toBeInTheDocument();
    });
  });

  it("shows an error when the API call fails", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: { detail: "not found" },
      response: { status: 404 },
    });

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    await fillAndSubmit(container);

    await waitFor(() => {
      expect(
        screen.getByText(/failed to issue request/i),
      ).toBeInTheDocument();
    });
  });
});
