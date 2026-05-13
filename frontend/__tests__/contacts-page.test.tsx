/**
 * Unit tests for the paginated, searchable contacts list page.
 *
 * The API client and Next.js navigation hooks are mocked so the test
 * exercises just the size selector, search debounce, URL round-trip
 * and pagination controls.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import ContactsPage, {
  PAGE_SIZE_OPTIONS,
  resolvePageSize,
} from "@/app/contacts/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Stable client object so the page's useEffect deps are stable across
// re-renders (a fresh object would re-trigger the fetch).
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

// Stub out the create / edit / delete dialogs so this test doesn't have
// to drag in their own dependencies. They show up in the page tree but
// behave as inert children.
vi.mock("@/components/create-contact-dialog", () => ({
  CreateContactDialog: () => <div data-testid="create-dialog" />,
}));
vi.mock("@/components/edit-contact-dialog", () => ({
  EditContactDialog: () => null,
}));
vi.mock("@/components/delete-contact-dialog", () => ({
  DeleteContactDialog: () => null,
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
        birthday: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        days_until_birthday: null,
      })),
      total,
      next_cursor,
    },
    error: undefined,
    response: { status: 200 },
  };
}

const PAGE_1 = Array.from({ length: 10 }, (_, i) => ({
  id: `id-${i.toString().padStart(2, "0")}`,
  full_name: `User ${i.toString().padStart(2, "0")}`,
}));
const PAGE_2 = Array.from({ length: 10 }, (_, i) => ({
  id: `id-${(i + 10).toString().padStart(2, "0")}`,
  full_name: `User ${(i + 10).toString().padStart(2, "0")}`,
}));

beforeEach(() => {
  // resetAllMocks (not clearAllMocks) drains queued return values so
  // unconsumed mocks from one test don't leak into the next.
  vi.resetAllMocks();
  currentParams = new URLSearchParams();
  cleanup();
});

// ---------------------------------------------------------------------------
// resolvePageSize
// ---------------------------------------------------------------------------

describe("resolvePageSize", () => {
  it("falls back to the default when the URL value is missing", () => {
    expect(resolvePageSize(null)).toBe(10);
    expect(resolvePageSize(undefined)).toBe(10);
  });

  it("falls back to the default for unknown values", () => {
    expect(resolvePageSize("999")).toBe(10);
    expect(resolvePageSize("not-a-number")).toBe(10);
  });

  it.each(PAGE_SIZE_OPTIONS.map((s) => s))(
    "accepts preset value %s",
    (size) => {
      expect(resolvePageSize(String(size))).toBe(size);
    },
  );
});

// ---------------------------------------------------------------------------
// ContactsPage — size selector + URL round-trip
// ---------------------------------------------------------------------------

describe("ContactsPage size selector", () => {
  it("fetches with the default page size when no ?size param is set", async () => {
    mockGet.mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3));

    render(<ContactsPage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query).toMatchObject({ limit: 10 });
    expect(mockGet.mock.calls[0][1].params.query.cursor).toBeUndefined();
    expect(mockGet.mock.calls[0][1].params.query.q).toBeUndefined();
  });

  it("honours ?size=5 from the URL on first render", async () => {
    currentParams = new URLSearchParams("size=5");
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<ContactsPage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query.limit).toBe(5);
  });

  it("falls back to the default when ?size is a nonsense value", async () => {
    currentParams = new URLSearchParams("size=12345");
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<ContactsPage />);

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    expect(mockGet.mock.calls[0][1].params.query.limit).toBe(10);
  });

  it("writes ?size=N to the URL when the selector changes", async () => {
    mockGet
      .mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"))
      .mockResolvedValueOnce(envelope(PAGE_1.slice(0, 5), 25, "id-04"));

    render(<ContactsPage />);
    await waitFor(() =>
      expect(screen.getByLabelText(/page size/i)).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText(/page size/i), {
      target: { value: "50" },
    });

    expect(mockReplace).toHaveBeenCalledWith("/contacts?size=50");
  });

  it("removes ?size from the URL when reverting to the default", async () => {
    currentParams = new URLSearchParams("size=5");
    mockGet
      .mockResolvedValueOnce(envelope([], 0))
      .mockResolvedValueOnce(envelope([], 0));

    render(<ContactsPage />);
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/page size/i), {
      target: { value: "10" },
    });

    expect(mockReplace).toHaveBeenCalledWith("/contacts");
  });
});

// ---------------------------------------------------------------------------
// ContactsPage — search box (debounced)
// ---------------------------------------------------------------------------

describe("ContactsPage search input", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    // Restore real timers so the pagination tests below (which rely on
    // ``waitFor``) aren't trapped behind a frozen clock.
    vi.useRealTimers();
  });

  it("does not fire a request on every keystroke", async () => {
    mockGet.mockResolvedValue(envelope(PAGE_1.slice(0, 3), 3));

    render(<ContactsPage />);
    await act(async () => {
      await vi.runAllTimersAsync();
    });
    expect(mockGet).toHaveBeenCalledTimes(1); // initial fetch only

    fireEvent.change(screen.getByLabelText(/search contacts/i), {
      target: { value: "a" },
    });
    fireEvent.change(screen.getByLabelText(/search contacts/i), {
      target: { value: "ad" },
    });
    fireEvent.change(screen.getByLabelText(/search contacts/i), {
      target: { value: "ada" },
    });

    // Before the debounce window elapses no extra request has fired.
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("debounces and writes ?q=... to the URL after the window elapses", async () => {
    mockGet.mockResolvedValue(envelope(PAGE_1.slice(0, 3), 3));

    render(<ContactsPage />);
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    fireEvent.change(screen.getByLabelText(/search contacts/i), {
      target: { value: "ada" },
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockReplace).toHaveBeenCalledWith("/contacts?q=ada");
  });

  it("removes ?q from the URL when the input is cleared", async () => {
    currentParams = new URLSearchParams("q=ada");
    mockGet.mockResolvedValue(envelope(PAGE_1.slice(0, 3), 3));

    render(<ContactsPage />);
    await act(async () => {
      await vi.runAllTimersAsync();
    });
    // Initial fetch carried the URL's q.
    expect(mockGet.mock.calls[0][1].params.query.q).toBe("ada");

    fireEvent.change(screen.getByLabelText(/search contacts/i), {
      target: { value: "" },
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });

    expect(mockReplace).toHaveBeenCalledWith("/contacts");
  });
});

// ---------------------------------------------------------------------------
// ContactsPage — pagination
// ---------------------------------------------------------------------------

describe("ContactsPage pagination controls", () => {
  it("hides pagination controls when the result fits in one page", async () => {
    mockGet.mockResolvedValueOnce(envelope(PAGE_1.slice(0, 3), 3));

    render(<ContactsPage />);
    await waitFor(() =>
      expect(screen.getByText(/3 contacts/i)).toBeInTheDocument(),
    );

    expect(screen.queryByTestId("pagination")).not.toBeInTheDocument();
  });

  it("shows 'Page X of Y' and walks pages via cursor", async () => {
    mockGet
      .mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"))
      .mockResolvedValueOnce(envelope(PAGE_2, 25, "id-19"));

    render(<ContactsPage />);
    await waitFor(() =>
      expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument(),
    );
    expect(mockGet.mock.calls[0][1].params.query.cursor).toBeUndefined();

    fireEvent.click(screen.getByLabelText(/next page/i));

    await waitFor(() =>
      expect(screen.getByText(/page 2 of 3/i)).toBeInTheDocument(),
    );
    expect(mockGet.mock.calls[1][1].params.query.cursor).toBe("id-09");
  });

  it("renders the empty state when no contacts match", async () => {
    mockGet.mockResolvedValueOnce(envelope([], 0));

    render(<ContactsPage />);
    await waitFor(() =>
      expect(
        screen.getByText(/no contacts yet|no contacts match/i),
      ).toBeInTheDocument(),
    );
  });

  it("keeps the table mounted with stale rows while a refetch is in flight", async () => {
    // First fetch resolves immediately so the table mounts with rows.
    mockGet.mockResolvedValueOnce(envelope(PAGE_1, 25, "id-09"));
    // Second fetch (triggered by Next click) hangs so the page is in
    // the loading-with-existing-data state when we make assertions.
    mockGet.mockReturnValueOnce(new Promise(() => {}));

    render(<ContactsPage />);
    await waitFor(() =>
      expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText(/next page/i));

    // The previous page's column headers and rows are still on screen
    // — i.e. we haven't unmounted the table while waiting for the
    // next response. ``aria-busy="true"`` signals the in-flight state
    // without remounting.
    expect(screen.getByText(/^name$/i)).toBeInTheDocument();
    expect(screen.getByText("User 00")).toBeInTheDocument();
    expect(
      document.querySelector('[aria-busy="true"]'),
    ).toBeInTheDocument();
  });

  it("treats an API error as zero results", async () => {
    mockGet.mockResolvedValueOnce({
      data: undefined,
      error: { title: "boom", status: 500 },
      response: { status: 500 },
    });

    render(<ContactsPage />);
    await waitFor(() =>
      expect(
        screen.getByText(/no contacts yet|no contacts match/i),
      ).toBeInTheDocument(),
    );
  });
});
