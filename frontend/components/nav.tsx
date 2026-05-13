/**
 * Top navigation bar shared across all dashboard pages.
 *
 * @module
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Cake, Settings } from "lucide-react";
import { Menu } from "@base-ui/react/menu";
import { SignOutButton } from "@/components/sign-out-button";
import { useAuth } from "@/lib/auth-context";

/**
 * Primary navigation bar with links to the main dashboard sections.
 *
 * Client Component so it can read the auth state for the sign-out button
 * and hide owner-only links when no user is signed in.
 */
export function Nav() {
  const { isAuthed } = useAuth();
  const pathname = usePathname();
  const isSignIn = pathname === "/sign-in";

  return (
    <header className="border-b bg-background">
      <div className="mx-auto max-w-5xl flex items-center gap-6 px-4 py-3">
        <Link
          href={isAuthed ? "/" : "/sign-in"}
          className="flex items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <Cake className="size-5 text-primary" />
          Birthday Tracker
        </Link>
        {isAuthed && !isSignIn && (
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
        <div className="ml-auto flex items-center gap-2">
          {isAuthed && !isSignIn && <SettingsMenu />}
          <SignOutButton />
        </div>
      </div>
    </header>
  );
}

/**
 * Gear-icon dropdown next to the sign-out button.
 *
 * Currently exposes a single item — **Account** — linking to
 * `/account`. The menu is structured so adding further entries
 * (Preferences, Billing, etc.) is just another `Menu.LinkItem`.
 */
function SettingsMenu() {
  return (
    <Menu.Root>
      <Menu.Trigger
        aria-label="Settings"
        className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
      >
        <Settings className="size-4" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={6} align="end">
          <Menu.Popup className="rounded-lg border border-border bg-popover py-1 text-sm shadow-md outline-none">
            <Menu.Item
              render={
                <Link
                  href="/account"
                  className="flex w-full cursor-pointer items-center px-3 py-1.5 hover:bg-muted focus:bg-muted outline-none"
                >
                  Account
                </Link>
              }
            />
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
