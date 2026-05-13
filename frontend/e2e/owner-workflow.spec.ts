/**
 * E2E Test 1: owner creates a contact and issues a collection request.
 *
 * Validates the full UI path from creating a contact through generating a
 * form link and verifying the pending (link-displayed) state.
 */

import { expect, test } from "@playwright/test";

test("owner creates a contact and issues a collection request", async ({
  page,
}) => {
  // ── Step 1: navigate to the contacts list ───────────────────────────────
  await page.goto("/contacts");

  // ── Step 2: open the "Add contact" dialog ───────────────────────────────
  await page.getByRole("button", { name: /add contact/i }).click();

  // ── Step 3: fill the required fields ────────────────────────────────────
  await page.getByLabel("Full name *").fill("E2E Owner Contact");
  await page.getByLabel("Email").fill("owner-e2e@example.com");

  // ── Step 4: save ─────────────────────────────────────────────────────────
  await page.getByRole("button", { name: /^save$/i }).click();

  // ── Step 5: contact appears in the list ─────────────────────────────────
  await expect(page.getByText("E2E Owner Contact")).toBeVisible();

  // ── Step 6: click "Send Request" for the new contact ────────────────────
  const contactRow = page.locator("tr", { hasText: "E2E Owner Contact" });
  await contactRow.getByRole("link", { name: /send request/i }).click();

  // ── Step 7: on the /contacts/new page with the contact pre-selected ──────
  await expect(page).toHaveURL(/contacts\/new/);

  // The email address is auto-filled from the contact record.
  await expect(page.getByLabel(/email address/i)).toHaveValue(
    "owner-e2e@example.com",
  );

  // ── Step 8: generate the form link ───────────────────────────────────────
  await page.getByRole("button", { name: /generate form link/i }).click();

  // ── Step 9: the pending form link is shown ───────────────────────────────
  await expect(
    page.getByText(/form link — send this to the contact/i),
  ).toBeVisible();
  await expect(page.getByText(/\/form\//)).toBeVisible();
});
