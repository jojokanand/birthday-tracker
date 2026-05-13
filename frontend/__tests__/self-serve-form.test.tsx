/**
 * Unit tests for the {@link SelfServeForm} component.
 *
 * The API client is mocked with `vi.mock` so no network calls occur.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SelfServeForm, messageForError } from "@/components/self-serve-form";

// ---------------------------------------------------------------------------
// Mock the API client
// ---------------------------------------------------------------------------

vi.mock("@/lib/api", () => ({
  apiClient: {
    POST: vi.fn(),
  },
}));

// The country dropdown and address autocomplete pull in heavy deps
// (base-ui Combobox, Google Maps SDK loader). Replace them with dumb
// stand-ins so the form-level tests stay focused on submit semantics.
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
// Two stub buttons: one that returns a place WITH a country (covers
// the `if (place.country)` true branch) and one with the country empty
// (covers the false branch).
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
    <>
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
      <button
        type="button"
        data-testid="autocomplete-stub-no-country"
        onClick={() =>
          onSelect({
            street1: "Some Street",
            city: "Townsville",
            region: "",
            postal_code: "",
            country: "",
          })
        }
      >
        Pick fake place (no country)
      </button>
    </>
  ),
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
  fireEvent.change(screen.getByLabelText(/^country$/i), { target: { value: "GB" } });
  fireEvent.change(screen.getByLabelText(/month/i), { target: { value: "12" } });
  fireEvent.change(screen.getByLabelText(/day/i), { target: { value: "10" } });
}

function renderForm() {
  return render(<SelfServeForm token="test.token" greetingName="Ada" />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("messageForError", () => {
  it.each([
    [410, undefined, /already been used or has expired/i],
    [404, undefined, /this form link is invalid/i],
    [500, undefined, /something went wrong/i],
    [undefined, undefined, /something went wrong/i],
  ])("status %s -> friendly fallback message", (status, error, expected) => {
    expect(messageForError(status, error)).toMatch(expected);
  });

  it("returns the first 422 detail with the 'Value error' prefix stripped", () => {
    const msg = messageForError(422, {
      errors: [
        { loc: ["body", "birthday"], msg: "Value error, invalid birthday: 02-29" },
      ],
    });
    expect(msg).toBe("invalid birthday: 02-29");
  });

  it.each<[string, unknown]>([
    ["non-object error", "boom"],
    ["null error", null],
    ["missing errors array", { detail: "huh" }],
    ["empty errors array", { errors: [] }],
    ["first entry not an object", { errors: ["nope"] }],
    ["first entry missing msg", { errors: [{ loc: ["body"] }] }],
    ["first entry msg is blank", { errors: [{ msg: "   " }] }],
  ])("falls back to the generic message when 422 detail is unusable (%s)", (_, error) => {
    expect(messageForError(422, error)).toMatch(/something went wrong/i);
  });
});

describe("SelfServeForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all required field labels", () => {
    renderForm();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/city/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^country$/i)).toBeInTheDocument();
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

  it("rejects Feb 29 in a non-leap year client-side and never calls the API", async () => {
    renderForm();
    fillRequiredFields();
    // Override the month/day picked by fillRequiredFields with an
    // impossible date for a non-leap year.
    fireEvent.change(screen.getByLabelText(/month/i), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/day/i), { target: { value: "29" } });
    fireEvent.change(screen.getByLabelText(/year/i), {
      target: { value: "1991" },
    });

    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/February 29 doesn't exist in 1991/i),
      ).toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("allows Feb 29 when no year is provided (leap-year probe)", async () => {
    mockPost.mockResolvedValue({
      response: { status: 204 },
      data: undefined,
      error: undefined,
    });

    renderForm();
    fillRequiredFields();
    fireEvent.change(screen.getByLabelText(/month/i), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/day/i), { target: { value: "29" } });

    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1].body.birthday).toEqual({
      month: 2,
      day: 29,
      year: null,
    });
  });

  it("surfaces the FastAPI 422 detail when the backend rejects the submission", async () => {
    mockPost.mockResolvedValue({
      response: { status: 422 },
      data: undefined,
      error: {
        title: "Request validation failed",
        status: 422,
        errors: [
          {
            loc: ["body", "birthday"],
            msg: "Value error, invalid birthday: 02-29",
            type: "value_error",
          },
        ],
      },
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid birthday: 02-29/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });

  it("shows the 'invalid link' message on 404 response", async () => {
    mockPost.mockResolvedValue({
      response: { status: 404 },
      data: undefined,
      error: { title: "Form not found", status: 404 },
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/this form link is invalid/i),
      ).toBeInTheDocument();
    });
  });

  it("falls back to the generic message on 422 with no usable detail", async () => {
    mockPost.mockResolvedValue({
      response: { status: 422 },
      data: undefined,
      error: { title: "Request validation failed", status: 422 },
    });

    renderForm();
    fillRequiredFields();
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
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

  it("submits a parsed birth_year when one is provided", async () => {
    mockPost.mockResolvedValue({
      response: { status: 204 },
      data: undefined,
      error: undefined,
    });

    renderForm();
    fillRequiredFields();
    // Fill the optional year — covers the non-empty branch of
    // birth_year's setValueAs transform.
    fireEvent.change(screen.getByLabelText(/year/i), {
      target: { value: "1990" },
    });

    fireEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1].body.birthday.year).toBe(1990);
  });

  it("preserves the existing country when the autocomplete returns no country", async () => {
    renderForm();
    fireEvent.click(screen.getByTestId("autocomplete-stub-no-country"));
    await waitFor(() =>
      expect(
        (screen.getByLabelText(/street address/i) as HTMLInputElement).value,
      ).toBe("Some Street"),
    );
    // Default country "US" was not overwritten.
    expect((screen.getByLabelText(/^country$/i) as HTMLInputElement).value).toBe(
      "US",
    );
  });

  it("populates address fields when an autocomplete suggestion is picked", async () => {
    mockPost.mockResolvedValue({
      response: { status: 204 },
      data: undefined,
      error: undefined,
    });

    renderForm();
    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: "Ada Lovelace" },
    });

    // Click the stub autocomplete; fillAddressFromPlace runs and writes
    // into the underlying form state.
    fireEvent.click(screen.getByTestId("autocomplete-stub"));

    await waitFor(() =>
      expect(
        (screen.getByLabelText(/street address/i) as HTMLInputElement).value,
      ).toBe("1 Place Drive"),
    );
    expect(
      (screen.getByLabelText(/^city \*$/i) as HTMLInputElement).value,
    ).toBe("Townsville");
    expect((screen.getByLabelText(/^country$/i) as HTMLInputElement).value).toBe(
      "US",
    );

    fireEvent.change(screen.getByLabelText(/month/i), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText(/day/i), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost.mock.calls[0][1].body.address).toMatchObject({
      street1: "1 Place Drive",
      city: "Townsville",
      region: "CA",
      postal_code: "94000",
      country: "US",
    });
  });
});
