/**
 * Home page — upcoming birthdays within a configurable window.
 *
 * Client Component: data is loaded from the backend with the signed-in
 * user's ID token. Wrapped in `<AuthGuard>` so anonymous visitors are
 * sent to `/sign-in`. The window selector (7 days through 1 year) is
 * persisted to the URL as `?days=N` so refreshing or sharing the link
 * preserves the state. Pagination is server-side at 10 contacts per
 * page; "Page X of Y" is computed from the page envelope's `total`.
 *
 * @module
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { AuthGuard } from "@/components/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  formatBirthday,
  formatDaysUntilBirthday,
  type ContactResponse,
} from "@/lib/format";

/** Window presets surfaced in the selector. */
export const WINDOW_PRESETS = [
  { label: "Next 7 days", days: 7 },
  { label: "Next 14 days", days: 14 },
  { label: "Next 30 days", days: 30 },
  { label: "Next 6 months", days: 183 },
  { label: "Next 1 year", days: 365 },
] as const;

/** Default window when no `?days=N` is present in the URL. */
const DEFAULT_DAYS = 30;

/** Page size for the upcoming-birthdays table. */
const PAGE_SIZE = 10;

/**
 * Resolve the window from a raw URL value to one of the {@link WINDOW_PRESETS}.
 *
 * Falls back to {@link DEFAULT_DAYS} when the value is missing, malformed,
 * or doesn't match a known preset — that way a hand-edited URL with a
 * nonsense value still renders the default view rather than 404'ing.
 */
export function resolveDays(raw: string | null | undefined): number {
  if (raw == null) return DEFAULT_DAYS;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) return DEFAULT_DAYS;
  const match = WINDOW_PRESETS.find((p) => p.days === parsed);
  return match ? match.days : DEFAULT_DAYS;
}

/**
 * Upcoming birthdays dashboard page.
 *
 * Wrapped in `<Suspense>` because `useSearchParams()` requires it in
 * Next.js 16, then in `<AuthGuard>` so unauthenticated users are
 * redirected to sign in.
 */
export default function HomePage() {
  return (
    <React.Suspense fallback={null}>
      <AuthGuard>
        <HomeContent />
      </AuthGuard>
    </React.Suspense>
  );
}

/** Inner component rendered only after the user is signed in. */
function HomeContent() {
  const api = useApiClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthed } = useAuth();

  const days = resolveDays(searchParams.get("days"));

  const [contacts, setContacts] = React.useState<ContactResponse[]>([]);
  const [total, setTotal] = React.useState(0);
  // Cursor stack lives in a ref so updating it after each fetch
  // doesn't re-trigger the fetch effect (which would loop).
  // pageCursors.current[i] is the cursor used to fetch page i;
  // pageCursors.current[0] is always null (the initial page).
  // Mutated only inside effects so the ``react-hooks/refs`` rule is happy.
  const pageCursors = React.useRef<(string | null)[]>([null]);

  // Reset paging when the window changes via the React-recommended
  // "store the prop in state and compare during render" pattern — see
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  // Doing this during render (not in an effect) avoids the cascade
  // that ``react-hooks/set-state-in-effect`` flags.
  const [prevDays, setPrevDays] = React.useState(days);
  const [pageIndex, setPageIndex] = React.useState(0);
  if (prevDays !== days) {
    setPrevDays(days);
    setPageIndex(0);
  }

  // The cursor stack itself is reset in an effect so we mutate the ref
  // outside of render. This effect runs before the fetch effect below
  // because effects fire in declaration order, so the fetch always
  // sees a fresh stack when ``days`` has just changed.
  React.useEffect(() => {
    pageCursors.current = [null];
  }, [days]);

  // ``loading`` is derived from "have we received the response for the
  // current (days, pageIndex) yet?" — that keeps the fetch effect free
  // of synchronous setState calls, and only the post-await branch
  // touches state.
  const fetchKey = `${days}|${pageIndex}`;
  const [lastCompletedKey, setLastCompletedKey] = React.useState<string | null>(
    null,
  );
  const loading = lastCompletedKey !== fetchKey;

  React.useEffect(() => {
    if (!isAuthed) return;
    let alive = true;
    (async () => {
      const cursor = pageCursors.current[pageIndex] ?? undefined;
      const { data, error } = await api.GET("/contacts", {
        params: {
          query: {
            upcoming_in_days: days,
            limit: PAGE_SIZE,
            ...(cursor ? { cursor } : {}),
          },
        },
      });
      if (!alive) return;
      if (error || !data) {
        setContacts([]);
        setTotal(0);
      } else {
        setContacts(data.items);
        setTotal(data.total);
        // Stash the next cursor so a subsequent Next click can fetch
        // the right page without us having to remember mid-flight state.
        pageCursors.current = pageCursors.current.slice(0, pageIndex + 1);
        pageCursors.current.push(data.next_cursor ?? null);
      }
      setLastCompletedKey(fetchKey);
    })();
    return () => {
      alive = false;
    };
  }, [api, isAuthed, days, pageIndex, fetchKey]);

  const onChangeDays = (newDays: number) => {
    const params = new URLSearchParams(searchParams.toString());
    if (newDays === DEFAULT_DAYS) params.delete("days");
    else params.set("days", String(newDays));
    const qs = params.toString();
    router.replace(qs ? `/?${qs}` : "/");
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasNext = pageIndex + 1 < totalPages;
  const hasPrev = pageIndex > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Upcoming Birthdays
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Contacts with a birthday in the selected window.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="window-select"
            className="text-sm text-muted-foreground"
          >
            Window
          </label>
          <select
            id="window-select"
            aria-label="Birthday window"
            value={days}
            onChange={(e) => onChangeDays(Number.parseInt(e.target.value, 10))}
            className="h-8 rounded-lg border border-input bg-background px-2 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
          >
            {WINDOW_PRESETS.map((p) => (
              <option key={p.days} value={p.days}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading upcoming…</div>
      ) : total === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <CalendarDays className="size-10 text-muted-foreground/50" />
            <p className="text-muted-foreground text-sm">
              No upcoming birthdays in this window.
            </p>
            <Link
              href="/contacts"
              className="text-sm text-primary underline underline-offset-4"
            >
              View all contacts →
            </Link>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>
              {WINDOW_PRESETS.find((p) => p.days === days)?.label ??
                `Next ${days} days`}
            </CardTitle>
            <CardDescription>
              {total} contact{total !== 1 ? "s" : ""} with an upcoming birthday.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Birthday</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>Contact</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      {c.preferred_name
                        ? `${c.preferred_name} (${c.full_name})`
                        : c.full_name}
                    </TableCell>
                    <TableCell>{formatBirthday(c.birthday)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          c.days_until_birthday === 0 ? "default" : "secondary"
                        }
                      >
                        {formatDaysUntilBirthday(c.days_until_birthday)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {c.email ?? c.phone ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
          {totalPages > 1 && (
            <div
              data-testid="pagination"
              className="flex items-center justify-between border-t px-4 py-3"
            >
              <span className="text-sm text-muted-foreground">
                Page {pageIndex + 1} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                  disabled={!hasPrev}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="size-4" />
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPageIndex((p) => p + 1)}
                  disabled={!hasNext}
                  aria-label="Next page"
                >
                  Next
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
