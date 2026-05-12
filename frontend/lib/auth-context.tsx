/**
 * Authentication context for the dashboard.
 *
 * Wraps the Firebase Web SDK with React hooks so components can call
 * `useAuth()` to get the current user, sign in, sign out, and (most
 * importantly) obtain a fresh ID token to send to the backend.
 *
 * @module
 */

"use client";

import * as React from "react";
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut as fbSignOut,
  type User as FirebaseUser,
} from "firebase/auth";
import { firebaseAuth, isFirebaseConfigured } from "@/lib/firebase";

/** Shape of the auth context. */
export interface AuthState {
  /** ``null`` until Firebase tells us; then either the user or ``undefined``. */
  user: FirebaseUser | null | undefined;
  /** ``true`` until Firebase has reported the first auth state. */
  loading: boolean;
  /** Trigger Google sign-in via a popup window. */
  signInWithGoogle: () => Promise<void>;
  /** Sign the current user out and clear local state. */
  signOut: () => Promise<void>;
  /**
   * Return a fresh ID token for the current user, or ``null`` when no
   * user is signed in. The Firebase SDK auto-refreshes tokens; pass
   * ``true`` to force a refresh immediately.
   */
  getIdToken: (forceRefresh?: boolean) => Promise<string | null>;
  /** ``true`` when the Firebase config env vars are present. */
  configured: boolean;
  /**
   * Treat the visitor as authenticated for the purposes of route guards
   * and navigation visibility. ``true`` when a real Firebase user is
   * signed in **or** when Firebase isn't configured at all — the latter
   * mirrors the backend's ``APP_ENV=development`` bypass so the app
   * stays usable in local dev / E2E without a real Firebase project.
   */
  isAuthed: boolean;
}

const AuthContext = React.createContext<AuthState | null>(null);

/**
 * Provider that wires Firebase Auth into React state.
 *
 * Place once near the root of the tree (typically inside the root
 * layout, around the page content).
 *
 * @param props.children Tree to render inside the provider.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const configured = isFirebaseConfigured();
  // Seed initial state from `configured` so unconfigured installs render
  // "signed out" immediately without an extra render cycle from inside an
  // effect (which the React 19 lint rule flags as a cascading render).
  const [user, setUser] = React.useState<FirebaseUser | null | undefined>(
    configured ? undefined : null,
  );
  const [loading, setLoading] = React.useState(configured);

  React.useEffect(() => {
    if (!configured) return;
    const auth = firebaseAuth();
    const unsubscribe = onAuthStateChanged(auth, (fbUser) => {
      setUser(fbUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, [configured]);

  const signInWithGoogle = React.useCallback(async () => {
    if (!configured) {
      throw new Error(
        "Firebase is not configured — NEXT_PUBLIC_FIREBASE_API_KEY is empty.",
      );
    }
    const auth = firebaseAuth();
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  }, [configured]);

  const signOut = React.useCallback(async () => {
    if (!configured) return;
    await fbSignOut(firebaseAuth());
  }, [configured]);

  const getIdToken = React.useCallback(
    async (forceRefresh = false): Promise<string | null> => {
      if (!configured) return null;
      const current = firebaseAuth().currentUser;
      if (!current) return null;
      return current.getIdToken(forceRefresh);
    },
    [configured],
  );

  const isAuthed = !configured || Boolean(user);
  const value = React.useMemo<AuthState>(
    () => ({
      user,
      loading,
      signInWithGoogle,
      signOut,
      getIdToken,
      configured,
      isAuthed,
    }),
    [user, loading, signInWithGoogle, signOut, getIdToken, configured, isAuthed],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to read the auth state from any Client Component.
 *
 * Throws if called outside an :class:`AuthProvider` — that's almost
 * always a programming error worth surfacing loudly.
 */
export function useAuth(): AuthState {
  const ctx = React.useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
