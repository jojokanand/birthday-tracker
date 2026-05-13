/**
 * Contacts list page — paginated, searchable address book.
 *
 * Page size (5 / 10 / 50) and search query (`q`) are persisted to the
 * URL as `?size=N` and `?q=...` so refreshing or sharing the link
 * keeps the view. Pagination is server-side at the chosen page size;
 * "Page X of Y" comes from the response envelope's `total`.
 *
 * @module
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Pencil, Search, Trash2, Users } from "lucide-react";
import { AuthGuard } from "@/components/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AddToCalendarMenu } from "@/components/add-to-calendar-menu";
import { CreateContactDialog } from "@/components/create-contact-dialog";
import { DeleteContactDialog } from "@/components/delete-contact-dialog";
import { EditContactDialog } from "@/components/edit-contact-dialog";
import { useApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { formatBirthday, type ContactResponse } from "@/lib/format";
import { useDebouncedValue } from "@/lib/use-debounced-value";

/** Page-size presets surfaced in the selector. */
export const PAGE_SIZE_OPTIONS = [5, 10, 50] as const;

/** Default page size when no `?size=N` is present in the URL. */
const DEFAULT_PAGE_SIZE = 10;

/** Debounce window for the search input. */
const SEARCH_DEBOUNCE_MS = 250;

/**
 * Map a raw URL value to one of the {@link PAGE_SIZE_OPTIONS}.
 *
 * Falls back to {@link DEFAULT_PAGE_SIZE} when the value is missing,
 * malformed, or doesn't match a preset — so a hand-edited URL can't
 * spike the request size beyond what the UI offers.
 */
export function resolvePageSize(raw: string | null | undefined): number {
  if (raw == null) return DEFAULT_PAGE_SIZE;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) return DEFAULT_PAGE_SIZE;
  return PAGE_SIZE_OPTIONS.find((s) => s === parsed) ?? DEFAULT_PAGE_SIZE;
}

/**
 * Contacts list page.
 *
 * Wrapped in `<Suspense>` because `useSearchParams()` requires it in
 * Next.js 16, then in `<AuthGuard>` so unauthenticated users are
 * redirected to sign in.
 */
export default function ContactsPage() {
  return (
    <React.Suspense fallback={null}>
      <AuthGuard>
        <ContactsContent />
      </AuthGuard>
    </React.Suspense>
  );
}

function ContactsContent() {
  const api = useApiClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthed } = useAuth();

  const pageSize = resolvePageSize(searchParams.get("size"));
  const urlQ = searchParams.get("q") ?? "";

  // Local input value drives the field; the debounced version is what
  // actually hits the API and the URL. Controlling the field directly
  // avoids the typing-feels-laggy problem the debounce would otherwise
  // create.
  const [qInput, setQInput] = React.useState(urlQ);
  const debouncedQ = useDebouncedValue(qInput, SEARCH_DEBOUNCE_MS);

  // If the URL changes externally (back button, shared link, dialog
  // refresh), pull the new value into the input via the
  // "track prop in state and compare during render" pattern. Doing it
  // mid-render avoids the cascade that ``react-hooks/set-state-in-effect``
  // flags.
  const [prevUrlQ, setPrevUrlQ] = React.useState(urlQ);
  if (prevUrlQ !== urlQ) {
    setPrevUrlQ(urlQ);
    setQInput(urlQ);
  }

  // Sync the URL when the debounced query changes — but only when the
  // user actually edited the input (debouncedQ differs from urlQ).
  // Without this guard we'd fight the browser's back/forward
  // navigation, which sets urlQ from the URL.
  React.useEffect(() => {
    if (debouncedQ === urlQ) return;
    const params = new URLSearchParams(searchParams.toString());
    if (debouncedQ) params.set("q", debouncedQ);
    else params.delete("q");
    const qs = params.toString();
    router.replace(qs ? `/contacts?${qs}` : "/contacts");
  }, [debouncedQ, urlQ, searchParams, router]);

  const [contacts, setContacts] = React.useState<ContactResponse[]>([]);
  const [total, setTotal] = React.useState(0);
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Per-row dialog state — only one of edit / delete is open at a time.
  const [editingContact, setEditingContact] =
    React.useState<ContactResponse | null>(null);
  const [deletingContact, setDeletingContact] =
    React.useState<ContactResponse | null>(null);

  // Same cursor-stack model as the home page: pageCursors.current[i]
  // is the cursor used to fetch page i (with [0] = null for the
  // initial page). Mutated only inside effects so the
  // ``react-hooks/refs`` rule is satisfied.
  const pageCursors = React.useRef<(string | null)[]>([null]);

  // Reset paging when the inputs that determine the result set change
  // (size, q, refreshKey from a successful create/edit/delete).
  // Tracked-in-state pattern so the comparison happens during render
  // without touching a ref, per React's
  // "Adjusting Some State When a Prop Changes" guidance.
  const resetKey = `${pageSize}|${debouncedQ}|${refreshKey}`;
  const [prevResetKey, setPrevResetKey] = React.useState(resetKey);
  const [pageIndex, setPageIndex] = React.useState(0);
  if (prevResetKey !== resetKey) {
    setPrevResetKey(resetKey);
    setPageIndex(0);
  }

  // Reset the cursor ref when the result-set inputs change — runs
  // before the fetch effect so the next fetch starts from the
  // beginning of the new set.
  React.useEffect(() => {
    pageCursors.current = [null];
  }, [pageSize, debouncedQ, refreshKey]);

  // Loading is derived from "have we received the response for the
  // current (resetKey, pageIndex) yet?" so the fetch effect doesn't
  // need a synchronous setState.
  const fetchKey = `${resetKey}|${pageIndex}`;
  const [lastCompletedKey, setLastCompletedKey] = React.useState<string | null>(
    null,
  );
  const loading = lastCompletedKey !== fetchKey;

  React.useEffect(() => {
    if (!isAuthed) return;
    let alive = true;
    (async () => {
      const cursor = pageCursors.current[pageIndex] ?? undefined;
      const trimmedQ = debouncedQ.trim();
      const { data, error } = await api.GET("/contacts", {
        params: {
          query: {
            limit: pageSize,
            ...(cursor ? { cursor } : {}),
            ...(trimmedQ ? { q: trimmedQ } : {}),
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
        pageCursors.current = pageCursors.current.slice(0, pageIndex + 1);
        pageCursors.current.push(data.next_cursor ?? null);
      }
      setLastCompletedKey(fetchKey);
    })();
    return () => {
      alive = false;
    };
  }, [api, isAuthed, pageSize, debouncedQ, pageIndex, refreshKey, fetchKey]);

  const refresh = React.useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const onChangePageSize = (newSize: number) => {
    const params = new URLSearchParams(searchParams.toString());
    if (newSize === DEFAULT_PAGE_SIZE) params.delete("size");
    else params.set("size", String(newSize));
    const qs = params.toString();
    router.replace(qs ? `/contacts?${qs}` : "/contacts");
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasNext = pageIndex + 1 < totalPages;
  const hasPrev = pageIndex > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {total} contact{total !== 1 ? "s" : ""}
            {debouncedQ.trim() ? ` matching "${debouncedQ.trim()}"` : ""}.
          </p>
        </div>
        <CreateContactDialog onCreated={refresh} />
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search
            aria-hidden
            className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none"
          />
          <Input
            type="search"
            aria-label="Search contacts"
            placeholder="Search by name or email…"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="page-size-select"
            className="text-sm text-muted-foreground"
          >
            Page size
          </label>
          <select
            id="page-size-select"
            aria-label="Page size"
            value={pageSize}
            onChange={(e) =>
              onChangePageSize(Number.parseInt(e.target.value, 10))
            }
            className="h-8 rounded-lg border border-input bg-background px-2 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
          >
            {PAGE_SIZE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Show the spinner-style line only on the very first paint —
          subsequent refreshes (search keystrokes, page navigation,
          create/edit/delete) keep the table mounted with the previous
          rows so the column headers don't flash. */}
      {loading && lastCompletedKey === null ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : total === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <Users className="size-10 text-muted-foreground/50" />
            <p className="text-muted-foreground text-sm">
              {debouncedQ.trim()
                ? `No contacts match "${debouncedQ.trim()}".`
                : "No contacts yet. Add one to get started."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent
            className="p-0"
            aria-busy={loading}
          >
            <Table className={loading ? "opacity-60 transition-opacity" : ""}>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email / Phone</TableHead>
                  <TableHead>Birthday</TableHead>
                  <TableHead>Address</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      <div>{c.full_name}</div>
                      {c.preferred_name && (
                        <div className="text-muted-foreground text-xs">
                          {c.preferred_name}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      <div>{c.email ?? "—"}</div>
                      {c.phone && <div className="text-xs">{c.phone}</div>}
                    </TableCell>
                    <TableCell>{formatBirthday(c.birthday)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.address
                        ? `${c.address.city}, ${c.address.country}`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${c.full_name}`}
                          onClick={() => setEditingContact(c)}
                        >
                          <Pencil className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${c.full_name}`}
                          onClick={() => setDeletingContact(c)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                        {c.birthday && <AddToCalendarMenu contact={c} />}
                        <Link
                          href={`/contacts/new?contact_id=${c.id}`}
                          className="inline-flex h-7 items-center rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium text-foreground transition-colors hover:bg-muted"
                        >
                          Send Request
                        </Link>
                      </div>
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

      <EditContactDialog
        contact={editingContact}
        open={editingContact !== null}
        onOpenChange={(open) => {
          if (!open) setEditingContact(null);
        }}
        onSaved={refresh}
      />
      <DeleteContactDialog
        contact={deletingContact}
        open={deletingContact !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingContact(null);
        }}
        onDeleted={refresh}
      />
    </div>
  );
}
