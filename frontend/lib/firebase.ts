/**
 * Firebase Web SDK initialisation.
 *
 * Configuration is read from `NEXT_PUBLIC_FIREBASE_*` env vars at build
 * time (they're baked into the client bundle — these values are not
 * secrets; Firebase Auth security comes from project rules + backend
 * token verification, not from hiding the config).
 *
 * In tests and dev-without-Firebase, the config can be left empty —
 * sign-in attempts will surface a clear error, but the rest of the app
 * still imports cleanly.
 *
 * @module
 */

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "",
};

/** True when at least the API key has been provided. */
export const isFirebaseConfigured = (): boolean =>
  Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);

/** Lazily build (or return the existing) singleton Firebase App. */
function getFirebaseApp(): FirebaseApp {
  const existing = getApps();
  if (existing.length > 0) return existing[0];
  return initializeApp(firebaseConfig);
}

/** Return the singleton Firebase Auth instance. */
export function firebaseAuth(): Auth {
  return getAuth(getFirebaseApp());
}
