/**
 * Unit tests for {@link DeleteContactDialog}.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { DeleteContactDialog } from "@/components/delete-contact-dialog";
import type { ContactResponse } from "@/lib/format";

const mockDelete = vi.fn();
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => ({ DELETE: mockDelete }),
}));

const CONTACT: ContactResponse = {
  id: "22222222-2222-4222-8222-222222222222",
  full_name: "Ada Lovelace",
  preferred_name: "Ada",
  email: "ada@example.com",
  phone: null,
  address: null,
  birthday: null,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  days_until_birthday: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockDelete.mockResolvedValue({ data: undefined, error: undefined });
});

describe("DeleteContactDialog", () => {
  it("renders nothing when no contact is supplied", () => {
    const { container } = render(
      <DeleteContactDialog
        contact={null}
        open={false}
        onOpenChange={() => {}}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("calls DELETE and signals onDeleted on confirm", async () => {
    const onOpenChange = vi.fn();
    const onDeleted = vi.fn();
    render(
      <DeleteContactDialog
        contact={CONTACT}
        open
        onOpenChange={onOpenChange}
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledTimes(1));
    expect(mockDelete).toHaveBeenCalledWith("/contacts/{contact_id}", {
      params: { path: { contact_id: CONTACT.id } },
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onDeleted).toHaveBeenCalled();
  });

  it("does NOT call DELETE when the user cancels", () => {
    const onOpenChange = vi.fn();
    const onDeleted = vi.fn();
    render(
      <DeleteContactDialog
        contact={CONTACT}
        open
        onOpenChange={onOpenChange}
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("renders an inline error and keeps the dialog open on DELETE failure", async () => {
    mockDelete.mockResolvedValue({ data: undefined, error: { detail: "no" } });
    const onOpenChange = vi.fn();
    const onDeleted = vi.fn();
    render(
      <DeleteContactDialog
        contact={CONTACT}
        open
        onOpenChange={onOpenChange}
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/failed to delete contact/i),
      ).toBeInTheDocument(),
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("uses the preferred-name + full-name format in the confirmation copy", () => {
    render(
      <DeleteContactDialog
        contact={CONTACT}
        open
        onOpenChange={() => {}}
      />,
    );
    // "Ada (Ada Lovelace)" — preferred + parenthesised full name.
    expect(screen.getByText(/Ada \(Ada Lovelace\)/)).toBeInTheDocument();
  });

  it("falls back to full name only when there is no preferred name", () => {
    render(
      <DeleteContactDialog
        contact={{ ...CONTACT, preferred_name: null }}
        open
        onOpenChange={() => {}}
      />,
    );
    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
  });
});
