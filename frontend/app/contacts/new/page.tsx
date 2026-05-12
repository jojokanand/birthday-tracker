/**
 * "Send collection request" page — selects a contact and issues a form link.
 *
 * Accepts an optional `contact_id` search parameter so the contacts list
 * can pre-fill the selector via `?contact_id=<uuid>`.
 *
 * @module
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { IssueRequestForm } from "@/components/issue-request-form";
import { apiClient } from "@/lib/api";
import type { ContactResponse } from "@/lib/format";

/** Always render at request time — this page reads live backend data. */
export const dynamic = "force-dynamic";

async function fetchContacts(): Promise<ContactResponse[]> {
  const { data, error } = await apiClient.GET("/contacts", {
    fetch: (input: RequestInfo | URL, init?: RequestInit) =>
      fetch(input, { ...init, cache: "no-store" }),
  });
  if (error) return [];
  return data ?? [];
}

/**
 * Props injected by Next.js App Router for pages with search params.
 */
interface PageProps {
  searchParams: Promise<{ contact_id?: string }>;
}

/**
 * Collection request page.
 *
 * Loads the full contact list server-side, then hands off rendering to the
 * interactive {@link IssueRequestForm} Client Component.
 */
export default async function NewCollectionRequestPage({
  searchParams,
}: PageProps) {
  const [contacts, params] = await Promise.all([
    fetchContacts(),
    searchParams,
  ]);
  const initialContactId = params.contact_id;

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
