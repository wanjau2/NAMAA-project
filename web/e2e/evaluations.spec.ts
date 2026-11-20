import { expect, test } from "@playwright/test";

/**
 * M10 — canonical patient evaluations on case detail.
 *
 * All four rule_evaluation outcomes must appear from the API, including
 * no-case results. Workflow stage stays separate. Review counts are not the
 * source of the outcome.
 */

test("Child A shows needs_review from the canonical evaluation", async ({
  page,
}) => {
  await page.goto("/cases/case-0001");
  await expect(page.getByRole("heading", { name: "Child A (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByRole("heading", { name: "Canonical evaluation" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page.getByText("Needs review").first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/Pending and rejected facts are not rule inputs/),
  ).toBeVisible();
  await expect(page.getByText("Identified", { exact: true })).toBeVisible();
  await expect(page.getByText("gateway stub", { exact: false })).toBeVisible();
});

test("Child B shows gap_identified from the canonical evaluation", async ({
  page,
}) => {
  await page.goto("/cases/case-0002");
  await expect(page.getByRole("heading", { name: "Child B (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page.getByText("Gap identified").first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Booked", { exact: true })).toBeVisible();
  await expect(
    page.getByText(/not a diagnosis and does not order a screening test/i),
  ).toBeVisible();
});

test("Adult D shows not_eligible with case null and keeps the invited workflow", async ({
  page,
}) => {
  await page.goto("/cases/case-0004");
  await expect(page.getByRole("heading", { name: "Adult D (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(page.getByText("Not eligible").first()).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("case: null")).toBeVisible();
  await expect(
    page.getByText(/not auto-closed, completed, or coerced/),
  ).toBeVisible();
  await expect(page.getByText("Invited", { exact: true })).toBeVisible();
  await expect(page.getByText("Declined", { exact: true })).toBeVisible();
});

test("Child F shows no gap in available data with case null and keeps closed completed", async ({
  page,
}) => {
  await page.goto("/cases/case-0006");
  await expect(page.getByRole("heading", { name: "Child F (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run evaluation" }).click();
  await expect(
    page.getByText("No gap identified in available data").first(),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByText(/Not an assurance of health/),
  ).toBeVisible();
  await expect(page.getByText("case: null")).toBeVisible();
  await expect(page.getByText("Closed", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("definition").filter({ hasText: "Preventive action completed" }),
  ).toBeVisible();
});
