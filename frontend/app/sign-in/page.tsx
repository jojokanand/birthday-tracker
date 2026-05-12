/**
 * Sign-in page.
 *
 * Public route — signed-in users are redirected away to the dashboard.
 * Currently only Google sign-in is wired up; add other providers by
 * extending {@link AuthState.signInWithGoogle}.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Cake } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";

/** Render the sign-in page. */
export default function SignInPage() {
  const { user, loading, signInWithGoogle, configured } = useAuth();
  const router = useRouter();
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  const handleClick = async () => {
    setError(null);
    setBusy(true);
    try {
      await signInWithGoogle();
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex justify-center py-16">
      <Card className="max-w-md w-full">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Cake className="size-6 text-primary" />
            <CardTitle>Birthday Tracker</CardTitle>
          </div>
          <CardDescription>
            Sign in to your account to manage your contacts.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {!configured && (
            <p className="text-destructive text-sm">
              Firebase is not configured. Set <code>NEXT_PUBLIC_FIREBASE_*</code>{" "}
              env vars and rebuild.
            </p>
          )}
          <Button onClick={handleClick} disabled={busy || !configured}>
            {busy ? "Signing in…" : "Sign in with Google"}
          </Button>
          {error && (
            <p className="text-destructive text-sm" role="alert">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
