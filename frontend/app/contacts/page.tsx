/**
 * Contacts list page — shows the caller's contacts with create / edit /
 * delete actions and a per-row "Send Request" link.
 *
 * @module
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { Pencil, Trash2, Users } from "lucide-react";
import { AuthGuard } from "@/components/auth-guard";
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
import { CreateContactDialog } from "@/components/create-contact-dialog";
import { DeleteContactDialog } from "@/components/delete-contact-dialog";
import { EditContactDialog } from "@/components/edit-contact-dialog";
import { useApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { formatBirthday, type ContactResponse } from "@/lib/format";

/**
 * Contacts list page.
 *
 * Fetches the caller's contacts client-side using the signed-in user's
 * ID token. The add / edit / delete dialogs all bump a refresh signal
 * on success to re-fetch the list.
 */
export default function ContactsPage() {
  return (
    <AuthGuard>
      <ContactsContent />
    </AuthGuard>
  );
}

function ContactsContent() {
  const api = useApiClient();
  const { isAuthed } = useAuth();
  const [contacts, setContacts] = React.useState<ContactResponse[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [refreshKey, setRefreshKey] = React.useState(0);

  // Per-action dialog state.  Only one of the two row dialogs is open
  // at a time, so a single ``activeContact`` value drives both.
  const [editingContact, setEditingContact] =
    React.useState<ContactResponse | null>(null);
  const [deletingContact, setDeletingContact] =
    React.useState<ContactResponse | null>(null);

  React.useEffect(() => {
    if (!isAuthed) return;
    let alive = true;
    (async () => {
      const { data, error } = await api.GET("/contacts", {});
      if (!alive) return;
      setContacts(error ? [] : (data ?? []));
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [api, isAuthed, refreshKey]);

  const refresh = React.useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {contacts.length} contact{contacts.length !== 1 ? "s" : ""} stored.
          </p>
        </div>
        <CreateContactDialog onCreated={refresh} />
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
                      {c.phone && <div className="text-xs">{c.phone}</div>}
                    </TableCell>
                    <TableCell>{formatBirthday(c.birthday)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.address
                        ? `${c.address.city}, ${c.address.country}`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
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
