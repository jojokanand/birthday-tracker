/**
 * Unit tests for {@link CreateContactDialog}.
 *
 * Mocks `useApiClient` so tests don't pull in the Firebase SDK and lets
 * us inspect exactly what `body` would be posted to `/contacts`.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { CreateContactDialog } from "@/components/create-contact-dialog";

// ---------------------------------------------------------------------------
// Mock the API client hook
// ---------------------------------------------------------------------------

const mockPost = vi.fn();
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => ({ POST: mockPost }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Open the dialog by clicking the "Add contact" trigger. */
function openDialog() {
  fireEvent.click(screen.getByRole("button", { name: /add contact/i }));
}

/** Submit the dialog. */
function clickSave() {
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
}

/** Click the "+ Add address" toggle so the address fields render. */
function expandAddress() {
  fireEvent.click(screen.getByRole("button", { name: /add address/i }));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CreateContactDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPost.mockResolvedValue({ data: { id: "x" }, error: undefined });
  });

  it("creates a contact with email only (no phone, no address)", async () => {
    render(<CreateContactDialog />);
    openDialog();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "ada@example.com" },
    });
    clickSave();

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    const body = mockPost.mock.calls[0][1].body;
    expect(body).toMatchObject({
      full_name: "Ada Lovelace",
      email: "ada@example.com",
      phone: null,
      address: null,
    });
  });

  it("posts a normalised E.164 phone number from the country-code picker", async () => {
    render(<CreateContactDialog />);
    openDialog();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });
    // Type a national-format US number; react-phone-number-input normalises
    // it to E.164 (+1...) given the default country is US.
    const phoneInput = screen
      .getByLabelText(/^phone$/i)
      .closest(".PhoneInput")
      ?.querySelector("input.PhoneInputInput") as HTMLInputElement;
    fireEvent.change(phoneInput, { target: { value: "(415) 555-2671" } });
    clickSave();

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    const body = mockPost.mock.calls[0][1].body;
    expect(body.phone).toBe("+14155552671");
    expect(body.email).toBeNull();
    expect(body.address).toBeNull();
  });

  it("posts the address when the address section is filled in", async () => {
    render(<CreateContactDialog />);
    openDialog();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "ada@example.com" },
    });

    expandAddress();
    fireEvent.change(screen.getByLabelText(/street address/i), {
      target: { value: "1 Main St" },
    });
    fireEvent.change(screen.getByLabelText(/^city$/i), {
      target: { value: "London" },
    });
    fireEvent.change(screen.getByLabelText(/country code/i), {
      target: { value: "gb" }, // lowercase: dialog uppercases on submit
    });

    clickSave();

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    const body = mockPost.mock.calls[0][1].body;
    expect(body.address).toEqual({
      street1: "1 Main St",
      street2: null,
      city: "London",
      region: null,
      postal_code: null,
      country: "GB",
    });
  });

  it("rejects a partial address (street without city/country)", async () => {
    render(<CreateContactDialog />);
    openDialog();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "ada@example.com" },
    });

    expandAddress();
    fireEvent.change(screen.getByLabelText(/street address/i), {
      target: { value: "1 Main St" },
    });
    // Wipe the default country to force the cross-field error.
    fireEvent.change(screen.getByLabelText(/country code/i), {
      target: { value: "" },
    });

    clickSave();

    await waitFor(() => {
      expect(screen.getByText(/address needs at least street/i)).toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });
});
