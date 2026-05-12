/**
 * Sign-out button used in the top navigation bar.
 *
 * @module
 */

"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

/**
 * Render a button that signs the current user out and redirects to /sign-in.
 *
 * Hidden until Firebase reports an auth state, so we don't briefly show
 * a "Sign out" button to anonymous visitors.
 */
export function SignOutButton() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  if (!user) return null;

  const handleClick = async () => {
    await signOut();
    router.replace("/sign-in");
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleClick}>
      <LogOut className="size-4" /> Sign out
    </Button>
  );
}
