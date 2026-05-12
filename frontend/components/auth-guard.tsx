/**
 * Client-side route guard.
 *
 * Renders children only when an authenticated Firebase user is present.
 * Redirects to `/sign-in` otherwise. Drop this near the top of any
 * Client Component tree that must be owner-only.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * Wrapper that redirects signed-out users to `/sign-in`.
 *
 * @param props.children Tree to render once a user is signed in.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!loading && !user) {
      router.replace("/sign-in");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex justify-center py-16 text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!user) {
    // Brief flash while the redirect runs.
    return null;
  }
  return <>{children}</>;
}
