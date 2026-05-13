/**
 * Unit tests for {@link EditContactDialog}.
 *
 * Mocks `useApiClient`, `CountrySelect`, and `AddressAutocomplete` so
 * the tests focus on dialog wiring + the PUT request body.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { EditContactDialog } from "@/components/edit-contact-dialog";
import type { ContactResponse } from "@/lib/format";

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

const mockPut = vi.fn();
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => ({ PUT: mockPut }),
}));

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
vi.mock("@/components/address-autocomplete", () => ({
  AddressAutocomplete: () => null,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_CONTACT: ContactResponse = {
  id: "11111111-1111-4111-8111-111111111111",
  full_name: "Ada Lovelace",
  preferred_name: "Ada",
  email: "ada@example.com",
  phone: "+14155551234",
  address: null,
  birthday: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  days_until_birthday: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockPut.mockResolvedValue({ data: { ...BASE_CONTACT }, error: undefined });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EditContactDialog", () => {
  it("renders nothing when no contact is supplied", () => {
    const { container } = render(
      <EditContactDialog
        contact={null}
        open={false}
        onOpenChange={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("pre-fills inputs from the contact", () => {
    render(
      <EditContactDialog
        contact={BASE_CONTACT}
        open
        onOpenChange={() => {}}
      />,
    );
    expect(
      (screen.getByLabelText(/full name/i) as HTMLInputElement).value,
    ).toBe("Ada Lovelace");
    expect(
      (screen.getByLabelText(/preferred name/i) as HTMLInputElement).value,
    ).toBe("Ada");
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).value).toBe(
      "ada@example.com",
    );
  });

  it("PUTs the updated body and closes on save", async () => {
    const onOpenChange = vi.fn();
    const onSaved = vi.fn();
    render(
      <EditContactDialog
        contact={BASE_CONTACT}
        open
        onOpenChange={onOpenChange}
        onSaved={onSaved}
      />,
    );

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Augusta Ada King" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
    expect(mockPut).toHaveBeenCalledWith("/contacts/{contact_id}", {
      params: { path: { contact_id: BASE_CONTACT.id } },
      body: expect.objectContaining({ full_name: "Augusta Ada King" }),
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onSaved).toHaveBeenCalled();
  });

  it("renders an inline error and keeps the dialog open on PUT failure", async () => {
    mockPut.mockResolvedValue({ data: undefined, error: { detail: "no" } });
    const onOpenChange = vi.fn();
    const onSaved = vi.fn();
    render(
      <EditContactDialog
        contact={BASE_CONTACT}
        open
        onOpenChange={onOpenChange}
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/failed to save changes/i),
      ).toBeInTheDocument(),
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("pre-fills the birthday inputs from contact.birthday", () => {
    render(
      <EditContactDialog
        contact={{
          ...BASE_CONTACT,
          birthday: { month: 12, day: 10, year: 1990 },
        }}
        open
        onOpenChange={() => {}}
      />,
    );
    // Birthday section auto-expands when the contact already has one.
    expect((screen.getByLabelText(/^month$/i) as HTMLInputElement).value).toBe(
      "12",
    );
    expect((screen.getByLabelText(/^day$/i) as HTMLInputElement).value).toBe(
      "10",
    );
    expect((screen.getByLabelText(/^year/i) as HTMLInputElement).value).toBe(
      "1990",
    );
  });

  it("PUTs an updated birthday", async () => {
    const onSaved = vi.fn();
    render(
      <EditContactDialog
        contact={{
          ...BASE_CONTACT,
          birthday: { month: 1, day: 1, year: 1990 },
        }}
        open
        onOpenChange={() => {}}
        onSaved={onSaved}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^year/i), {
      target: { value: "2000" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
    expect(mockPut.mock.calls[0][1].body.birthday).toEqual({
      month: 1,
      day: 1,
      year: 2000,
    });
  });

  it("flattens an existing address into the form so it's pre-filled", () => {
    render(
      <EditContactDialog
        contact={{
          ...BASE_CONTACT,
          address: {
            street1: "1 Main St",
            street2: null,
            city: "Townsville",
            region: "CA",
            postal_code: "94000",
            country: "US",
          },
        }}
        open
        onOpenChange={() => {}}
      />,
    );
    // Address section should be expanded since the contact has one.
    expect(
      (screen.getByLabelText(/street address/i) as HTMLInputElement).value,
    ).toBe("1 Main St");
    expect((screen.getByLabelText(/^city$/i) as HTMLInputElement).value).toBe(
      "Townsville",
    );
    expect((screen.getByLabelText(/^country$/i) as HTMLInputElement).value).toBe(
      "US",
    );
  });
});
