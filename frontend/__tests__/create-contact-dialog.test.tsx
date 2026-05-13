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

// Replace the heavy CountrySelect and AddressAutocomplete components
// with dumb stand-ins so we can drive the country field via fireEvent
// and skip the Maps SDK altogether.
vi.mock("@/components/country-select", () => ({
  CountrySelect: ({
    id,
    value,
    onChange,
  }: {
    id?: string;
    value: string;
    onChange: (v: string) => void;
  }) => (
    <input
      id={id}
      aria-label="Country"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));
// Stub AddressAutocomplete with a button that fires the parent's
// `onSelect` callback so tests can drive the place-fill code path.
vi.mock("@/components/address-autocomplete", () => ({
  AddressAutocomplete: ({
    onSelect,
  }: {
    onSelect: (p: {
      street1: string;
      city: string;
      region: string;
      postal_code: string;
      country: string;
    }) => void;
  }) => (
    <button
      type="button"
      data-testid="autocomplete-stub"
      onClick={() =>
        onSelect({
          street1: "1 Place Drive",
          city: "Townsville",
          region: "CA",
          postal_code: "94000",
          country: "us",
        })
      }
    >
      Pick fake place
    </button>
  ),
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
    fireEvent.change(screen.getByLabelText(/^country$/i), {
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
    fireEvent.change(screen.getByLabelText(/^country$/i), {
      target: { value: "" },
    });

    clickSave();

    await waitFor(() => {
      expect(screen.getByText(/address needs at least street/i)).toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("populates every address field when an autocomplete suggestion is picked", async () => {
    render(<CreateContactDialog />);
    openDialog();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "ada@example.com" },
    });

    // Open the address section, then click the stub Autocomplete button.
    expandAddress();
    fireEvent.click(screen.getByTestId("autocomplete-stub"));

    await waitFor(() =>
      expect(
        (screen.getByLabelText(/street address/i) as HTMLInputElement).value,
      ).toBe("1 Place Drive"),
    );
    expect((screen.getByLabelText(/^city$/i) as HTMLInputElement).value).toBe(
      "Townsville",
    );
    expect((screen.getByLabelText(/^country$/i) as HTMLInputElement).value).toBe(
      "US", // uppercased by fillAddressFromPlace
    );

    clickSave();
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1].body.address).toEqual({
      street1: "1 Place Drive",
      street2: null,
      city: "Townsville",
      region: "CA",
      postal_code: "94000",
      country: "US",
    });
  });

  it("closes without an API call when the user cancels", () => {
    render(<CreateContactDialog />);
    openDialog();
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Discard me" },
    });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("renders inline validation errors for the required fields", async () => {
    render(<CreateContactDialog />);
    openDialog();
    // Submit immediately — full_name and the email-or-phone refinement
    // both fail, so error messages render under the matching fields.
    clickSave();
    await waitFor(() => {
      expect(screen.getByText(/^required$/i)).toBeInTheDocument();
    });
    expect(
      screen.getByText(/at least one of email or phone/i),
    ).toBeInTheDocument();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("shows a server error message when the POST fails", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
    });

    render(<CreateContactDialog />);
    openDialog();
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada" },
    });
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "ada@example.com" },
    });
    clickSave();

    await waitFor(() =>
      expect(screen.getByText(/failed to create contact/i)).toBeInTheDocument(),
    );
  });

  it("re-opens the address section when the autocomplete fires while collapsed", async () => {
    render(<CreateContactDialog />);
    openDialog();
    // Manually expand once so the stub button is mounted, then collapse.
    expandAddress();
    expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
    // Click "Hide address" to collapse.
    fireEvent.click(screen.getByRole("button", { name: /hide address/i }));
    expect(screen.queryByLabelText(/street address/i)).not.toBeInTheDocument();

    // Re-expand and trigger the autocomplete; the helper sets
    // `addressOpen=true` so the section is visible afterwards.
    expandAddress();
    fireEvent.click(screen.getByTestId("autocomplete-stub"));
    await waitFor(() =>
      expect(screen.getByLabelText(/street address/i)).toBeInTheDocument(),
    );
  });
});
