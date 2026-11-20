import { expect, test } from "@playwright/test";
import { setRole } from "./helpers";

/**
 * The retrieved-context view (Alfred's M3 rendering rules).
 *
 * Live data is verified-context records plus Relate hints. Contract examples
 * stay labelled. Absence of a record is never a finding of absence.
 */

test("live backend retrieves verified records without inventing assembled metadata", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await expect(page.getByRole("heading", { name: "Retrieved context" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Verified context" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText("No verified-context service is available"),
  ).toHaveCount(0);
  await expect(
    page.getByText(/not exhaustive/).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/absence of a record here is not evidence/i),
  ).toBeVisible();
  await expect(
    page.getByText(/do not authorize access, imply caregiver authority, or establish eligibility/),
  ).toBeVisible();
  await expect(page.getByText(/No query, tier or assembled-item metadata/)).toBeVisible();
  await expect(page.getByText("Partial", { exact: true })).toBeVisible();
});

test("a denied context retrieve is an access outcome, not a finding of no records", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/context");
  await expect(page.getByRole("heading", { name: "Verified context" })).toBeVisible({
    timeout: 20_000,
  });
  await setRole(page, "population_analyst");
  await expect(page.getByText("Not available in this session")).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/not a clinical finding/i),
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

test("the review screen shows nested issues, source hash and simulated model identity", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/\[missing_date\]/).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText(/means not reported, not “none found”/i),
  ).toHaveCount(0);
  await expect(page.getByText(/source hash/).first()).toBeVisible();
  await expect(
    page.getByText("simulated", { exact: true }).first(),
  ).toBeVisible();
});

test("a review decision is journaled and labelled as a stub FHIR commit", async ({
  page,
}) => {
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await setRole(page, "clinical_reviewer");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });

  const firstCard = page.locator("article").first();
  await expect(firstCard.getByRole("checkbox").first()).toBeVisible();
  for (const box of await firstCard.getByRole("checkbox").all()) {
    await box.check();
  }
  await firstCard.getByRole("button", { name: "Accept" }).click();

  await expect(
    page.getByText(/Recorded in this synthetic workspace/).first(),
  ).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/not a HAPI commit/i).first()).toBeVisible();
  await expect(
    page.getByText(/Accepted by reviewer/).first(),
  ).toBeVisible();
});
