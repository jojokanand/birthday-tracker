/**
 * E2E Tests 2 & 3: contact submits the self-serve form; owner sees the result.
 *
 * A contact + collection request are created via the API in `beforeAll` so
 * the form token is available before any browser interaction.  Tests run
 * serially because Test 3 depends on the submission from Test 2.
 */

import { expect, test } from "@playwright/test";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Birthday set to 3 days from today so it falls in the 30-day dashboard window. */
function upcomingBirthday(): { month: number; day: number } {
  const d = new Date();
  d.setDate(d.getDate() + 3);
  return { month: d.getMonth() + 1, day: d.getDate() };
}

test.describe.serial("Contact self-serve form and dashboard", () => {
  let formToken: string;
  const greetingName = "FormE2E";

  test.beforeAll(async ({ request }) => {
    // Create a contact with a preferred name (used as greeting).
    const contactResp = await request.post(`${API_URL}/contacts`, {
      data: {
        full_name: "E2E Form Contact",
        preferred_name: greetingName,
        email: "form-e2e@example.com",
      },
    });
    expect(contactResp.ok()).toBeTruthy();
    const contact = await contactResp.json();

    // Issue a collection request → get the form URL.
    const reqResp = await request.post(`${API_URL}/collection-requests`, {
      data: {
        contact_id: contact.id,
        channel: "email",
        destination: "form-e2e@example.com",
      },
    });
    expect(reqResp.ok()).toBeTruthy();
    const { form_url } = await reqResp.json();

    // Extract the token segment: http://localhost:3000/form/<token>
    formToken = form_url.split("/form/")[1];
  });

  // ── Test 2 ─────────────────────────────────────────────────────────────
  test("contact opens the form link and submits all fields", async ({
    page,
  }) => {
    await page.goto(`/form/${formToken}`);

    // Greeting is rendered from the server-fetched metadata.
    await expect(page.getByText(`Hi ${greetingName}`)).toBeVisible();

    // Fill the self-serve form.
    await page.getByLabel("Full name *").fill("E2E Form Contact");
    await page.getByLabel("Street address *").fill("42 Playwright Ave");
    await page.getByLabel("City *").fill("Testville");
    await page.getByLabel("Country code *").fill("US");

    const { month, day } = upcomingBirthday();
    await page.locator("#birth_month").fill(String(month));
    await page.locator("#birth_day").fill(String(day));

    await page.getByRole("button", { name: /submit/i }).click();

    // Confirmation message shown on success.
    await expect(
      page.getByText(`Thank you, ${greetingName}!`),
    ).toBeVisible();
  });

  // ── Test 3 ─────────────────────────────────────────────────────────────
  test("owner sees the new contact on the dashboard with upcoming birthday", async ({
    page,
  }) => {
    await page.goto("/");

    // The home page lists contacts with a birthday in the next 30 days.
    // Our contact's birthday is 3 days out, so it must appear.
    await expect(page.getByText("E2E Form Contact")).toBeVisible();
  });
});
