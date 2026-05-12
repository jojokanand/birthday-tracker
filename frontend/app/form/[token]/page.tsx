/**
 * Public form page — shown when a contact clicks their form link.
 *
 * Fetches form metadata server-side (validates the token, gets the greeting
 * name and channel) then renders the interactive {@link SelfServeForm}.
 *
 * @module
 */

import { notFound } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SelfServeForm } from "@/components/self-serve-form";
import { apiClient } from "@/lib/api";

interface PageProps {
  params: Promise<{ token: string }>;
}

/**
 * Contact-facing form page.
 *
 * A 404 from the API (invalid or expired token) surfaces as a Next.js
 * `notFound()` so the framework renders the standard not-found UI.  A 410
 * (already fulfilled) is shown as a friendly message.
 */
export default async function FormPage({ params }: PageProps) {
  const { token } = await params;

  const { data, response } = await apiClient.GET("/form/{token}", {
    params: { path: { token } },
    fetch: (input: RequestInfo | URL, init?: RequestInit) =>
      fetch(input, { ...init, cache: "no-store" }),
  });

  if (response.status === 404) {
    notFound();
  }

  if (response.status === 410) {
    return (
      <div className="flex justify-center py-16">
        <Card className="max-w-md w-full text-center">
          <CardContent className="py-12">
            <p className="text-lg font-semibold mb-2">Link already used</p>
            <p className="text-muted-foreground text-sm">
              This form link has already been submitted or has expired. If you
              think this is a mistake, ask the sender for a new link.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) {
    notFound();
  }

  return (
    <div className="flex justify-center py-8">
      <Card className="max-w-lg w-full">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            Hi {data.greeting_name}! 👋
          </CardTitle>
          <CardDescription>
            Please fill in your details below. This link expires on{" "}
            <strong>
              {new Date(data.expires_at).toLocaleDateString("en", {
                dateStyle: "medium",
              })}
            </strong>{" "}
            and can only be used once.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SelfServeForm token={token} greetingName={data.greeting_name} />
        </CardContent>
      </Card>
    </div>
  );
}
