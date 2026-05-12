/**
 * Typed HTTP client for the Birthday Tracker backend.
 *
 * Re-exports `createClient` from `openapi-fetch` pre-wired with the
 * generated types.  Import `apiClient` for server components and
 * `browserApiClient` for client components (same base URL, named exports
 * for clarity).
 *
 * @module
 */

import createClient from "openapi-fetch";
import type { paths } from "./api-types";

/** Base URL read from the environment (falls back to localhost for local dev).
 *
 * `||` (not `??`) because the deploy workflow passes the build arg as an
 * empty string when `BACKEND_URL` is unset (first deploy) — `??` would let
 * that through and break URL parsing during the Next.js build.
 */
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Pre-configured `openapi-fetch` client typed against the backend's OpenAPI
 * schema.  Use this in both Server and Client Components — the same client
 * instance works in both contexts since `openapi-fetch` uses the global
 * `fetch`.
 */
export const apiClient = createClient<paths>({ baseUrl: BASE_URL });

// Re-export component types for convenience in page/component files.
export type { paths };
