/**
 * Home page — upcoming birthdays within the next 30 days.
 *
 * Data is fetched server-side on every request so the list is always fresh.
 *
 * @module
 */

import Link from "next/link";
import { CalendarDays } from "lucide-react";
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
import { apiClient } from "@/lib/api";
import {
  formatBirthday,
  formatDaysUntilBirthday,
  type ContactResponse,
} from "@/lib/format";

/** Number of look-ahead days for the upcoming birthdays list. */
const UPCOMING_DAYS = 30;

async function fetchUpcoming(): Promise<ContactResponse[]> {
  const { data, error } = await apiClient.GET("/contacts", {
    params: { query: { upcoming_in_days: UPCOMING_DAYS } },
    fetch: (input: RequestInfo | URL, init?: RequestInit) =>
      fetch(input, { ...init, cache: "no-store" }),
  });
  if (error) return [];
  return data ?? [];
}

/**
 * Upcoming birthdays dashboard page.
 *
 * Shows contacts whose birthday falls within the next {@link UPCOMING_DAYS}
 * days, ordered nearest-first.  Server-renders for fresh data on every
 * navigation.
 */
export default async function HomePage() {
  const contacts = await fetchUpcoming();

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
