/**
 * Top navigation bar shared across all dashboard pages.
 *
 * @module
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Cake } from "lucide-react";
import { SignOutButton } from "@/components/sign-out-button";
import { useAuth } from "@/lib/auth-context";

/**
 * Primary navigation bar with links to the main dashboard sections.
 *
 * Client Component so it can read the auth state for the sign-out button
 * and hide owner-only links when no user is signed in.
 */
export function Nav() {
  const { user } = useAuth();
  const pathname = usePathname();
  const isSignIn = pathname === "/sign-in";

  return (
    <header className="border-b bg-background">
      <div className="mx-auto max-w-5xl flex items-center gap-6 px-4 py-3">
        <Link
          href={user ? "/" : "/sign-in"}
          className="flex items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <Cake className="size-5 text-primary" />
          Birthday Tracker
        </Link>
        {user && !isSignIn && (
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link href="/" className="hover:text-foreground transition-colors">
              Upcoming
            </Link>
            <Link
              href="/contacts"
              className="hover:text-foreground transition-colors"
            >
              Contacts
            </Link>
            <Link
              href="/contacts/new"
              className="hover:text-foreground transition-colors"
            >
              Send Request
            </Link>
          </nav>
        )}
        <div className="ml-auto">
          <SignOutButton />
        </div>
      </div>
    </header>
  );
}
