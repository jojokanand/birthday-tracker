/**
 * Contacts list page — shows all stored contacts with add/delete actions.
 *
 * @module
 */

import Link from "next/link";
import { Users } from "lucide-react";
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
import { CreateContactDialog } from "@/components/create-contact-dialog";
import { apiClient } from "@/lib/api";
import { formatBirthday, type ContactResponse } from "@/lib/format";

async function fetchContacts(): Promise<ContactResponse[]> {
  const { data, error } = await apiClient.GET("/contacts", {
    fetch: (input: RequestInfo | URL, init?: RequestInit) =>
      fetch(input, { ...init, cache: "no-store" }),
  });
  if (error) return [];
  return data ?? [];
}

/**
 * Contacts list page.
 *
 * Server-renders the full contact list; the add-contact dialog and delete
 * actions are Client Components embedded within.
 */
export default async function ContactsPage() {
  const contacts = await fetchContacts();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {contacts.length} contact{contacts.length !== 1 ? "s" : ""} stored.
          </p>
        </div>
        <CreateContactDialog />
      </div>

      {contacts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <Users className="size-10 text-muted-foreground/50" />
            <p className="text-muted-foreground text-sm">
              No contacts yet. Add one to get started.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>All contacts</CardTitle>
            <CardDescription>
              Click &ldquo;Send Request&rdquo; to issue a collection-request form
              link for any contact.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email / Phone</TableHead>
                  <TableHead>Birthday</TableHead>
                  <TableHead>Address</TableHead>
                  <TableHead />
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
                      {c.phone && (
                        <div className="text-xs">{c.phone}</div>
                      )}
                    </TableCell>
                    <TableCell>{formatBirthday(c.birthday)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.address
                        ? `${c.address.city}, ${c.address.country}`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/contacts/new?contact_id=${c.id}`}
                        className="inline-flex h-7 items-center rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium text-foreground transition-colors hover:bg-muted"
                      >
                        Send Request
                      </Link>
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
