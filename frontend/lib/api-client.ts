/**
 * Authenticated API client factory.
 *
 * Wraps `openapi-fetch` with a `fetch` override that attaches the
 * caller's current Firebase ID token as an `Authorization: Bearer` header.
 * Components obtain a client via {@link useApiClient} so the token is
 * always fresh.
 *
 * @module
 */

"use client";

import * as React from "react";
import createClient, { type Client } from "openapi-fetch";
import type { paths } from "./api-types";
import { useAuth } from "@/lib/auth-context";

/** Backend base URL — baked into the bundle via NEXT_PUBLIC_API_URL at build time. */
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Hook that returns an `openapi-fetch` client whose every request carries
 * the signed-in user's ID token (when one is available).
 *
 * The client itself is memoised by reference to the auth context, so
 * components passing it to children don't trigger re-renders on each
 * call.
 */
export function useApiClient(): Client<paths> {
  const { getIdToken } = useAuth();
  return React.useMemo(() => {
    const authedFetch: typeof fetch = async (input, init) => {
      const token = await getIdToken();
      const headers = new Headers(init?.headers);
      if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return fetch(input, { ...init, headers, cache: "no-store" });
    };
    return createClient<paths>({ baseUrl: BASE_URL, fetch: authedFetch });
  }, [getIdToken]);
}
