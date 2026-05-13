/**
 * Account page — shows the signed-in owner's identity-derived details.
 *
 * Read-only for now: the four fields (first name, last name, email,
 * phone) come straight from the Firebase ID-token claims via
 * `GET /me`. Edits to those values are a Firebase / Google account
 * concern, not an app concern.
 *
 * @module
 */

"use client";

import * as React from "react";
import { AuthGuard } from "@/components/auth-guard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

/** Shape of the four fields we render. */
interface AccountFields {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
}

/**
 * Account page entry point.
 *
 * Wrapped in `<AuthGuard>` so unauthenticated visitors are redirected
 * to `/sign-in` rather than seeing a blank page or a 401-flash.
 */
export default function AccountPage() {
  return (
    <AuthGuard>
      <AccountContent />
    </AuthGuard>
  );
}

/** Inner component rendered only after the user is signed in. */
function AccountContent() {
  const api = useApiClient();
  const { isAuthed } = useAuth();
  const [fields, setFields] = React.useState<AccountFields | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!isAuthed) return;
    let alive = true;
    (async () => {
      const { data, error } = await api.GET("/me", {});
      if (!alive) return;
      if (error || !data) {
        setFields(null);
      } else {
        setFields({
          first_name: data.first_name,
          last_name: data.last_name,
          email: data.email,
          phone: data.phone,
        });
      }
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [api, isAuthed]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Account</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Your sign-in details. To edit, update them in your Google account.
        </p>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>
            Sourced from the account you signed in with.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3 text-sm">
              <Field label="First name" value={fields?.first_name} />
              <Field label="Last name" value={fields?.last_name} />
              <Field label="Email" value={fields?.email} />
              <Field label="Phone" value={fields?.phone} />
            </dl>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** One row of the definition list — muted "—" when the value is null. */
function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">
        {value ? value : <span className="text-muted-foreground">—</span>}
      </dd>
    </>
  );
}
