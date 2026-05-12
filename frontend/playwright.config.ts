/**
 * Playwright configuration for Birthday Tracker E2E tests.
 *
 * In CI (when the `CI` environment variable is set) only Chromium is used.
 * Locally, Chromium, WebKit, and Firefox are all exercised.
 *
 * The Next.js dev server is started automatically via `webServer`; the backend
 * must already be running (or started by the CI workflow) on port 8000 before
 * Playwright is invoked.
 *
 * @module
 */

import { defineConfig, devices } from "@playwright/test";

const BASE_URL = "http://localhost:3000";
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",

  fullyParallel: false,

  forbidOnly: !!process.env.CI,

  retries: process.env.CI ? 1 : 0,

  reporter: [
    ["html", { open: "never" }],
    ["list"],
  ],

  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    video: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: process.env.CI
    ? [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }]
    : [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
        { name: "webkit", use: { ...devices["Desktop Safari"] } },
        { name: "firefox", use: { ...devices["Desktop Firefox"] } },
      ],

  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      NEXT_PUBLIC_API_URL: API_URL,
    },
  },
});
