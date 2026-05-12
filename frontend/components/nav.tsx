/**
 * Top navigation bar shared across all dashboard pages.
 *
 * @module
 */

import Link from "next/link";
import { Cake } from "lucide-react";

/**
 * Primary navigation bar with links to the main dashboard sections.
 *
 * This is a Server Component — no client-side interactivity needed.
 */
export function Nav() {
  return (
    <header className="border-b bg-background">
      <div className="mx-auto max-w-5xl flex items-center gap-6 px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <Cake className="size-5 text-primary" />
          Birthday Tracker
        </Link>
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
      </div>
    </header>
  );
}
