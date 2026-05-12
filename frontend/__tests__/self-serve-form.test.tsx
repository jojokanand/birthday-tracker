/**
 * Unit tests for the {@link SelfServeForm} component.
 *
 * The API client is mocked with `vi.mock` so no network calls occur.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SelfServeForm } from "@/components/self-serve-form";

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
// Helpers
// ---------------------------------------------------------------------------

/**
 * Fill every required field of the self-serve form using `fireEvent` so that
 * react-hook-form's internal state is updated correctly (including
 * `valueAsNumber` for number inputs).
 */
function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Ada Lovelace" } });
  fireEvent.change(screen.getByLabelText(/street address/i), { target: { value: "1 Main St" } });
  fireEvent.change(screen.getByLabelText(/city/i), { target: { value: "London" } });
  fireEvent.change(screen.getByLabelText(/country code/i), { target: { value: "GB" } });
  fireEvent.change(screen.getByLabelText(/month/i), { target: { value: "12" } });
  fireEvent.change(screen.getByLabelText(/day/i), { target: { value: "10" } });
}

function renderForm() {
  return render(<SelfServeForm token="test.token" greetingName="Ada" />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SelfServeForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all required field labels", () => {
    renderForm();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/city/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/country code/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/month/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/day/i)).toBeInTheDocument();
  });

  it("shows thank-you message on successful submission", async () => {
    mockPost.mockResolvedValue({
      response: { status: 204 },
      data: undefined,
      error: undefined,
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/thank you, ada/i)).toBeInTheDocument();
    });
  });

  it("shows 'already used' error on 410 response", async () => {
    mockPost.mockResolvedValue({
      response: { status: 410 },
      data: undefined,
      error: { detail: "gone" },
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/already been used or has expired/i),
      ).toBeInTheDocument();
    });
  });

  it("shows generic error on server failure", async () => {
    mockPost.mockResolvedValue({
      response: { status: 500 },
      data: undefined,
      error: { detail: "server error" },
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
  });

  it("shows validation errors when required fields are empty", async () => {
    renderForm();

    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/required/i).length).toBeGreaterThan(0);
    });

    expect(mockPost).not.toHaveBeenCalled();
  });
});
