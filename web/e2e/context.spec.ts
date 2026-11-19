import { expect, test } from "@playwright/test";

/**
 * The retrieved-context view (Alfred's M3 rendering rules).
 *
 * The claims under test are absence claims: an empty result must read as
 * unknown, a missing service must not read as a finding, and the
 * non-exhaustive notice must always be present.
 */

test("with no backend service, absence of context is not a finding", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await expect(page.getByRole("heading", { name: "Retrieved context" })).toBeVisible();

  await expect(
    page.getByText("No verified-context service is available"),
  ).toBeVisible();
  await expect(
    page.getByText(/absence of a service, not a finding that no records exist/i),
  ).toBeVisible();
});

test("context is not a diagnosis, permission or eligibility decision", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await expect(
    page.getByText(
      /not a diagnosis, a permission, a clinical risk or an eligibility decision/i,
    ),
  ).toBeVisible();
});

test("a loaded envelope shows completeness, scope and the non-exhaustive notice", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await page.getByRole("button", { name: "Contract example" }).click();

  await expect(page.getByText("Contract example — not backend data")).toBeVisible();
  await expect(page.getByText("Partial", { exact: true })).toBeVisible();
  await expect(page.getByText(/Checked scope/)).toBeVisible();
  await expect(
    page.getByText(/not exhaustive/).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/absence of a record here is not evidence/i),
  ).toBeVisible();

  // The item carries its reference, version and verification markers.
  await expect(page.getByText("Observation/demo-observation")).toBeVisible();
  await expect(page.getByText("Structured")).toBeVisible();
  await expect(page.getByText("Source verified")).toBeVisible();
  await expect(page.getByText("Not reviewed by a clinician")).toBeVisible();
});

test("an empty result renders as unknown, never as nothing found", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await page.getByRole("button", { name: "Empty result" }).click();

  await expect(
    page.getByText(/Unknown — nothing was returned/),
  ).toBeVisible();
  await expect(
    page.getByText(/empty result, not a finding of absence/i),
  ).toBeVisible();
  await expect(page.getByText("Unknown", { exact: true }).first()).toBeVisible();
});

test("the review screen states that issues are not reported by this API", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText(/means not reported, not “none found”/i).first(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/source hash/).first()).toBeVisible();
  // exact: otherwise it matches the simulation bar's "Simulated role" label.
  await expect(
    page.getByText("simulated", { exact: true }).first(),
  ).toBeVisible();
});

test("a review decision says plainly that it did not persist", async ({ page }) => {
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });

  // Switch to the reviewer role so the controls are live.
  const toggle = page.getByRole("button", { name: "Session" });
  if (await toggle.isVisible().catch(() => false)) await toggle.click();
  await page.getByLabel("Simulated role").last().selectOption("clinical_reviewer");

  await page.getByRole("button", { name: "Accept" }).first().click();

  // The client attempts the real endpoint and reports exactly why it failed.
  await expect(
    page.getByText(/no fact-review endpoint yet|Not sent:/i).first(),
  ).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByText(/not an authorization receipt|will not invent one/i).first(),
  ).toBeVisible();
});
