/**
 * Home page — upcoming birthdays within the next 30 days.
 *
 * Client Component: data is loaded from the backend with the signed-in
 * user's ID token. Wrapped in `<AuthGuard>` so anonymous visitors are
 * sent to `/sign-in`.
 *
 * @module
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { AuthGuard } from "@/components/auth-guard";
import { Badge } from "@/components/ui/badge";
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

/** Number of look-ahead days for the upcoming birthdays list. */
const UPCOMING_DAYS = 30;

/**
 * Upcoming birthdays dashboard page.
 *
 * Shows contacts whose birthday falls within the next {@link UPCOMING_DAYS}
 * days, ordered nearest-first.
 */
export default function HomePage() {
  return (
    <AuthGuard>
      <HomeContent />
    </AuthGuard>
  );
}

/** Inner component rendered only after the user is signed in. */
function HomeContent() {
  const api = useApiClient();
  const { isAuthed } = useAuth();
  const [contacts, setContacts] = React.useState<ContactResponse[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!isAuthed) return;
    let alive = true;
    (async () => {
      const { data, error } = await api.GET("/contacts", {
        params: { query: { upcoming_in_days: UPCOMING_DAYS } },
      });
      if (!alive) return;
      setContacts(error ? [] : (data ?? []));
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [api, isAuthed]);

  if (loading) {
    return (
      <div className="text-sm text-muted-foreground">Loading upcoming…</div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Upcoming Birthdays
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Contacts with a birthday in the next {UPCOMING_DAYS} days.
        </p>
      </div>

      {contacts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <CalendarDays className="size-10 text-muted-foreground/50" />
            <p className="text-muted-foreground text-sm">
              No upcoming birthdays in the next {UPCOMING_DAYS} days.
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
            <CardTitle>Next {UPCOMING_DAYS} days</CardTitle>
            <CardDescription>
              {contacts.length} contact{contacts.length !== 1 ? "s" : ""} with
              an upcoming birthday.
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
        </Card>
      )}
    </div>
  );
}
