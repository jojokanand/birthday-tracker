/**
 * Unit tests for the {@link IssueRequestForm} component.
 *
 * Mocks the {@link useApiClient} hook so tests don't pull in the
 * Firebase SDK.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import {
  IssueRequestForm,
  maskDestination,
} from "@/components/issue-request-form";
import type { ContactResponse } from "@/lib/format";

// ---------------------------------------------------------------------------
// Mock the API client hook
// ---------------------------------------------------------------------------

const mockPost = vi.fn();
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => ({ POST: mockPost }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

const FORM_URL = "https://example.com/form/abc.def";

function envelope({
  sent = false,
  channel = "email",
  destination = "ada@example.com",
}: {
  sent?: boolean;
  channel?: "email" | "sms";
  destination?: string;
} = {}) {
  return {
    data: {
      request_id: "req-1",
      contact_id: ADA_ID,
      channel,
      destination,
      expires_at: "2030-01-01T00:00:00Z",
      form_url: FORM_URL,
      sent,
    },
    error: undefined,
    response: { status: 201 },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Pick Ada + email channel + destination, then click the named button. */
function selectAdaWithEmail(container: HTMLElement) {
  const contactSelect = container.querySelector<HTMLSelectElement>("#contact_id")!;
  fireEvent.change(contactSelect, { target: { value: ADA_ID } });
  fireEvent.click(screen.getByDisplayValue("email"));
  const destInput = container.querySelector<HTMLInputElement>("#destination")!;
  fireEvent.change(destInput, { target: { value: "ada@example.com" } });
}

// ---------------------------------------------------------------------------
// maskDestination
// ---------------------------------------------------------------------------

describe("maskDestination", () => {
  it("masks email local-parts but keeps the domain", () => {
    expect(maskDestination("email", "ada@example.com")).toBe("a***@example.com");
    expect(maskDestination("email", "x@y.com")).toBe("x***@y.com");
  });

  it("returns the value unchanged when the email is malformed", () => {
    expect(maskDestination("email", "no-at-sign")).toBe("no-at-sign");
  });

  it("masks phone numbers down to the last four digits", () => {
    expect(maskDestination("sms", "+12125551234")).toBe("(***) ***-1234");
    expect(maskDestination("sms", "555-9999")).toBe("(***) ***-9999");
  });

  it("falls back to four asterisks when there are no digits", () => {
    expect(maskDestination("sms", "no digits")).toBe("(***) ***-****");
  });
});

// ---------------------------------------------------------------------------
// IssueRequestForm
// ---------------------------------------------------------------------------

describe("IssueRequestForm", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders contact names in the selector", () => {
    render(<IssueRequestForm contacts={CONTACTS} />);
    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
    expect(screen.getByText(/Charles Babbage/)).toBeInTheDocument();
  });

  it("Generate form link sends `send: false` and shows the URL", async () => {
    mockPost.mockResolvedValue(envelope({ sent: false }));

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    selectAdaWithEmail(container);
    fireEvent.click(screen.getByRole("button", { name: /generate form link/i }));

    await waitFor(() => expect(screen.getByText(FORM_URL)).toBeInTheDocument());
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][1].body.send).toBe(false);
    // No "Sent to" line on the generate path.
    expect(screen.queryByText(/sent to/i)).not.toBeInTheDocument();
  });

  it("Send via Email sends `send: true` and shows the masked destination", async () => {
    mockPost.mockResolvedValue(
      envelope({ sent: true, channel: "email", destination: "ada@example.com" }),
    );

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    selectAdaWithEmail(container);
    fireEvent.click(screen.getByRole("button", { name: /send via email/i }));

    await waitFor(() => expect(screen.getByText(/sent to/i)).toBeInTheDocument());
    expect(mockPost.mock.calls[0][1].body.send).toBe(true);
    expect(screen.getByText("a***@example.com")).toBeInTheDocument();
    // The form URL stays available as a fallback.
    expect(screen.getByText(FORM_URL)).toBeInTheDocument();
  });

  it("relabels the Send button when the channel switches to SMS", () => {
    render(
      <IssueRequestForm contacts={CONTACTS} initialContactId={CHARLES_ID} />,
    );
    expect(
      screen.getByRole("button", { name: /send via sms/i }),
    ).toBeInTheDocument();
  });

  it("renders a PhoneInput in the SMS branch instead of a plain input", () => {
    render(
      <IssueRequestForm contacts={CONTACTS} initialContactId={CHARLES_ID} />,
    );
    // react-phone-number-input adds the ``PhoneInput`` class to the wrapper
    // so we can detect it without coupling to the country dropdown's
    // exact internals.
    const wrapper = document.querySelector(".PhoneInput");
    expect(wrapper).not.toBeNull();
  });

  it("surfaces the 503 detail when the notifier isn't configured", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: { detail: "SMS delivery is not configured for this server." },
      response: { status: 503 },
    });

    render(<IssueRequestForm contacts={CONTACTS} initialContactId={CHARLES_ID} />);
    // Charles has a phone, no email — channel defaults to sms.
    fireEvent.click(screen.getByRole("button", { name: /send via sms/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/sms delivery is not configured/i),
      ).toBeInTheDocument(),
    );
  });

  it("falls back to a generic message when the API returns an unhelpful error", async () => {
    mockPost.mockResolvedValue({
      data: undefined,
      error: {},
      response: { status: 500 },
    });

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    selectAdaWithEmail(container);
    fireEvent.click(screen.getByRole("button", { name: /generate form link/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to issue request/i)).toBeInTheDocument(),
    );
  });

  it("auto-fills destination from the selected contact", () => {
    const { container } = render(
      <IssueRequestForm contacts={CONTACTS} initialContactId={ADA_ID} />,
    );
    const destInput = container.querySelector<HTMLInputElement>("#destination")!;
    expect(destInput.value).toBe("ada@example.com");
  });

  it("copies the form URL to the clipboard when 'Copy' is clicked", async () => {
    mockPost.mockResolvedValue(envelope({ sent: false }));

    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    const { container } = render(<IssueRequestForm contacts={CONTACTS} />);
    selectAdaWithEmail(container);
    fireEvent.click(screen.getByRole("button", { name: /generate form link/i }));
    await waitFor(() => screen.getByText(FORM_URL));

    fireEvent.click(screen.getByRole("button", { name: /^copy$/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(FORM_URL));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /copied!/i }),
      ).toBeInTheDocument(),
    );
  });
});
