/**
 * "Send collection request" page — selects a contact and issues a form link.
 *
 * Accepts an optional `contact_id` search parameter so the contacts list
 * can pre-fill the selector via `?contact_id=<uuid>`.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { AuthGuard } from "@/components/auth-guard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { IssueRequestForm } from "@/components/issue-request-form";
import { useApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ContactResponse } from "@/lib/format";

/**
 * Collection request page.
 *
 * Loads the caller's contact list client-side, then renders the
 * interactive {@link IssueRequestForm}.
 */
export default function NewCollectionRequestPage() {
  return (
    <AuthGuard>
      <NewCollectionRequestContent />
    </AuthGuard>
  );
}

function NewCollectionRequestContent() {
  const api = useApiClient();
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const initialContactId = searchParams.get("contact_id") ?? undefined;

  const [contacts, setContacts] = React.useState<ContactResponse[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!user) return;
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
  }, [api, user]);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Send Form Request</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Generate a secure, time-limited link and send it to a contact so they
          can fill in their birthday and address.
        </p>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Issue collection request</CardTitle>
          <CardDescription>
            The link expires in 7 days and can only be used once.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <IssueRequestForm
            contacts={contacts}
            initialContactId={initialContactId}
          />
        </CardContent>
      </Card>
    </div>
  );
}
