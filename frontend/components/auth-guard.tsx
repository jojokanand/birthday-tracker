/**
 * Client-side route guard.
 *
 * Renders children only when the visitor is treated as authenticated.
 * Redirects to `/sign-in` otherwise. Drop this near the top of any
 * Client Component tree that must be owner-only.
 *
 * When Firebase isn't configured (local dev / E2E), the guard treats
 * the visitor as signed in — this mirrors the backend's
 * ``APP_ENV=development`` bypass so the dashboard is usable without a
 * real Firebase project.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * Wrapper that redirects un-authed visitors to `/sign-in`.
 *
 * @param props.children Tree to render once the visitor is authed.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthed, loading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!loading && !isAuthed) {
      router.replace("/sign-in");
    }
  }, [loading, isAuthed, router]);

  if (loading) {
    return (
      <div className="flex justify-center py-16 text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (!isAuthed) {
    // Brief flash while the redirect runs.
    return null;
  }
  return <>{children}</>;
}
