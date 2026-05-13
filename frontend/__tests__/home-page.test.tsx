/**
 * Unit tests for the upcoming-birthdays home page.
 *
 * The API client and Next.js navigation hooks are mocked so the test
 * exercises just the window selector + cursor pagination behaviour.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  cleanup,
} from "@testing-library/react";
import HomePage, {
  WINDOW_PRESETS,
  resolveDays,
} from "@/app/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Stable client object so the home page's useEffect deps are stable
// across re-renders (a fresh object would re-trigger the fetch).
const mockApiClient = { GET: vi.fn() };
const mockGet = mockApiClient.GET;
vi.mock("@/lib/api-client", () => ({
  useApiClient: () => mockApiClient,
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthed: true, loading: false }),
}));

const mockReplace = vi.fn();
let currentParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => currentParams,
}));

// Build a paginated envelope shaped like the live API.
function envelope(
  items: Array<{ id: string; full_name: string }>,
  total: number,
  next_cursor: string | null = null,
) {
  return {
    data: {
      items: items.map((c) => ({
        id: c.id,
        full_name: c.full_name,
        preferred_name: null,
        email: null,
        phone: null,
        address: null,
        birthday: { month: 6, day: 15, year: null },
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        days_until_birthday: 5,
      })),
      total,
      next_cursor,
    },
    error: undefined,
    response: { status: 200 },
  };
}

// 25 contacts → three pages (10 + 10 + 5).
const PAGE_1 = Array.from({ length: 10 }, (_, i) => ({
  id: `id-${i.toString().padStart(2, "0")}`,
  full_name: `User ${i.toString().padStart(2, "0")}`,
}));
const PAGE_2 = Array.from({ length: 10 }, (_, i) => ({
  id: `id-${(i + 10).toString().padStart(2, "0")}`,
  full_name: `User ${(i + 10).toString().padStart(2, "0")}`,
}));
const PAGE_3 = Array.from({ length: 5 }, (_, i) => ({
  id: `id-${(i + 20).toString().padStart(2, "0")}`,
  full_name: `User ${(i + 20).toString().padStart(2, "0")}`,
}));

beforeEach(() => {
  // resetAllMocks (not clearAllMocks) drains queued
  // ``mockResolvedValueOnce`` values so unconsumed mocks from one test
  // don't leak into the next.
  vi.resetAllMocks();
  currentParams = new URLSearchParams();
  cleanup();
});

// ---------------------------------------------------------------------------
// resolveDays
// ---------------------------------------------------------------------------

describe("resolveDays", () => {
  it("returns the default when the URL value is missing", () => {
    expect(resolveDays(null)).toBe(30);
    expect(resolveDays(undefined)).toBe(30);
  });

  it("returns the default when the URL value isn't a known preset", () => {
    expect(resolveDays("999")).toBe(30);
    expect(resolveDays("not-a-number")).toBe(30);
  });

  it.each(WINDOW_PRESETS.map((p) => p.days))(
    "accepts preset value %s",
    (days) => {
      expect(resolveDays(String(days))).toBe(days);
    },
  );
});

// ---------------------------------------------------------------------------
// HomePage — selector + initial fetch
// ---------------------------------------------------------------------------

describe("HomePage window selector", () => {
  it("fetches with the default 30-day window when no ?days param is set", async () => {
    mockGet.mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3));

    render(<HomePage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query).toMatchObject({
      upcoming_in_days: 30,
      limit: 10,
    });
    expect(mockGet.mock.calls[0][1].params.query.cursor).toBeUndefined();
  });

  it("honours ?days=7 from the URL on first render", async () => {
    currentParams = new URLSearchParams("days=7");
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<HomePage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query.upcoming_in_days).toBe(7);
  });

  it("falls back to the default when ?days is a nonsense value", async () => {
    currentParams = new URLSearchParams("days=12345");
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<HomePage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query.upcoming_in_days).toBe(30);
  });

  it("writes ?days=N to the URL when the selector changes", async () => {
    mockGet
      .mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3))
      .mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3));

    render(<HomePage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/birthday window/i)).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText(/birthday window/i), {
      target: { value: "7" },
    });

    expect(mockReplace).toHaveBeenCalledWith("/?days=7");
  });

  it("removes ?days from the URL when reverting to the default 30 days", async () => {
    currentParams = new URLSearchParams("days=7");
    mockGet
      .mockResolvedValueOnce(envelope([], 0))
      .mockResolvedValueOnce(envelope([], 0));

    render(<HomePage />);
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/birthday window/i), {
      target: { value: "30" },
    });

    expect(mockReplace).toHaveBeenCalledWith("/");
  });
});

// ---------------------------------------------------------------------------
// HomePage — cursor pagination
// ---------------------------------------------------------------------------

describe("HomePage pagination controls", () => {
  it("hides the pagination controls when the result fits in one page", async () => {
    mockGet.mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3));

    render(<HomePage />);
    await waitFor(() =>
      expect(screen.getByText(/3 contacts/i)).toBeInTheDocument(),
    );

    expect(screen.queryByTestId("pagination")).not.toBeInTheDocument();
  });

  it("shows 'Page X of Y' and walks through pages via cursor", async () => {
    mockGet
      .mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"))
      .mockResolvedValueOnce(envelope(PAGE_2, 25, "id-19"))
      .mockResolvedValueOnce(envelope(PAGE_3, 25, null));

    render(<HomePage />);

    await waitFor(() =>
      expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument(),
    );
    expect(mockGet.mock.calls[0][1].params.query.cursor).toBeUndefined();

    fireEvent.click(screen.getByLabelText(/next page/i));

    await waitFor(() =>
      expect(screen.getByText(/page 2 of 3/i)).toBeInTheDocument(),
    );
    expect(mockGet.mock.calls[1][1].params.query.cursor).toBe("id-09");

    fireEvent.click(screen.getByLabelText(/next page/i));

    await waitFor(() =>
      expect(screen.getByText(/page 3 of 3/i)).toBeInTheDocument(),
    );
    expect(mockGet.mock.calls[2][1].params.query.cursor).toBe("id-19");
    // On the final page Next is disabled.
    expect(screen.getByLabelText(/next page/i)).toBeDisabled();
  });

  it("Prev navigates back through previously seen cursors", async () => {
    mockGet
      .mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"))
      .mockResolvedValueOnce(envelope(PAGE_2, 25, "id-19"))
      .mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"));

    render(<HomePage />);
    await waitFor(() =>
      expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument(),
    );
    // Prev disabled on the first page.
    expect(screen.getByLabelText(/previous page/i)).toBeDisabled();

    fireEvent.click(screen.getByLabelText(/next page/i));
    await waitFor(() =>
      expect(screen.getByText(/page 2 of 3/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText(/previous page/i));
    await waitFor(() =>
      expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument(),
    );
    // Page 1 was re-fetched without a cursor.
    expect(mockGet.mock.calls[2][1].params.query.cursor).toBeUndefined();
  });

  it("renders the empty state when the window has no upcoming birthdays", async () => {
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<HomePage />);
    await waitFor(() =>
      expect(
        screen.getByText(/no upcoming birthdays in this window/i),
      ).toBeInTheDocument(),
    );
  });

  it("treats an API error as zero results", async () => {
    mockGet.mockResolvedValueOnce({
      data: undefined,
      error: { title: "boom", status: 500 },
      response: { status: 500 },
    });

    render(<HomePage />);
    await waitFor(() =>
      expect(
        screen.getByText(/no upcoming birthdays in this window/i),
      ).toBeInTheDocument(),
    );
  });
});
