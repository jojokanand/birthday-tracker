/**
 * Vitest configuration for the birthday-tracker frontend.
 *
 * @module
 */

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["**/node_modules/**", "**/e2e/**"],
    coverage: {
      // Only measure code that is reasonable to unit-test without
      // standing up a real Firebase / Maps SDK / Next.js runtime.
      // Pages and auth glue are exercised by Playwright E2E.
      include: ["components/**", "lib/**"],
      exclude: [
        // Generated from openapi.json
        "lib/api-types.ts",
        // Trivial wrappers / SDK init that need full third-party mocks
        "lib/api.ts",
        "lib/api-client.ts",
        "lib/auth-context.tsx",
        "lib/firebase.ts",
        "lib/utils.ts",
        // shadcn/base-ui primitives — covered by the components that
        // compose them
        "components/ui/**",
        // Auth-context-bound widgets — exercised by E2E
        "components/auth-guard.tsx",
        "components/sign-out-button.tsx",
        "components/nav.tsx",
      ],
      thresholds: {
        statements: 90,
        branches: 90,
        functions: 90,
        lines: 90,
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
});
