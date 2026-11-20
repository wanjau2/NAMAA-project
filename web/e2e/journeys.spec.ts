import { expect, test } from "@playwright/test";
import { expectApiConnected, setRole, waitForWorklist } from "./helpers";

/**
 * E1 — both synthetic journeys end to end against the live API.
 *
 * These assert the safety properties as a reviewer would see them, not just
 * that pages load: a booking cannot complete care, closure needs evidence and
 * a reviewer, and missing information blocks approval.
 */

test.describe("guest entry and worklist", () => {
  test("a fresh session reaches the worklist without credentials", async ({ page }) => {
    await page.goto("/");
    // Rendered as a long or short label depending on width.
    await expect(page.getByTestId("sim-notice")).toBeVisible();
    await expect(page.getByTestId("sim-notice")).toContainText(
      "SYNTHETIC DEMO DATA",
    );
    await expect(page.getByText("Synthetic demonstration only")).toBeVisible();

    await page.getByRole("link", { name: /Start Synthetic Demo Session/ }).click();
    await waitForWorklist(page);
    await expectApiConnected(page);

    // Served by the API, not a fixture.
    await expect(page.getByText("Child A (synthetic)")).toBeVisible();
    await expect(page.getByText(/of\s*6\s*synthetic cases/)).toBeVisible();
  });

  test("the simulation notice is present on every screen", async ({ page }) => {
    for (const path of ["/", "/cases", "/metrics", "/cases/case-0001"]) {
      await page.goto(path);
      await expect(page.getByTestId("sim-notice")).toBeVisible();
    }
  });
});

test.describe("child journey — Child B, booked to completed", () => {
  test("booking cannot complete care; attendance then evidence can", async ({ page }) => {
    await page.goto("/cases/case-0002");
    await expect(page.getByRole("heading", { name: "Child B (synthetic)" })).toBeVisible();

    // At `booked`, closure must not even be offered.
    await expect(page.getByRole("button", { name: /^Close as completed/ })).toHaveCount(0);

    // Coordinator records attendance.
    await setRole(page, "coordinator");
    await page.getByRole("button", { name: /^Record attendance/ }).click();
    await page.getByLabel("Outcome").selectOption("attended");
    await page.locator("form").getByRole("button", { name: "Record attendance", exact: true }).click();
    await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
    await expect(
      page.getByText(/booked\/active → attended\/active/).first(),
    ).toBeVisible();

    // Closure is a clinical-reviewer action; the coordinator sees the boundary.
    await page.reload();
    const closeRow = page.getByRole("button", { name: /^Close as completed/ });
    await expect(closeRow).toHaveAttribute("aria-disabled", "true");
    await expect(
      page.getByText(/Requires the Clinical Reviewer role/).first(),
    ).toBeVisible();

    // Reviewer closes with evidence and attestation.
    await setRole(page, "clinical_reviewer");
    await closeRow.click();
    await expect(
      page.getByText(/The only disposition that increases the completed-care count/),
    ).toBeVisible();

    // Attempt without an evidence reference: the server refuses.
    await page.getByLabel(/I authorize closure/).check();
    await page.locator("form").getByRole("button", { name: "Close as completed", exact: true }).click();
    await expect(page.getByText("This field is required.")).toBeVisible();

    // Entered input must survive the failure (D002 §4).
    await expect(page.getByLabel(/I authorize closure/)).toBeChecked();

    await page.getByLabel("Evidence reference").fill("Encounter/enc-synthetic-02");
    await page.locator("form").getByRole("button", { name: "Close as completed", exact: true }).click();
    await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();

    await page.reload();
    await expect(
      page.getByText("Preventive action completed").first(),
    ).toBeVisible();
    // Appears in both the case header and the audit timeline.
    await expect(
      page.getByText(/Encounter\/enc-synthetic-02/).first(),
    ).toBeVisible();
  });
});

test.describe("adult journey — Adult C, rejected referral stays owned", () => {
  test("a rejected referral blocks completion until it is reassigned", async ({ page }) => {
    await page.goto("/cases/case-0003");
    await expect(page.getByRole("heading", { name: "Adult C (synthetic)" })).toBeVisible();
    await expect(page.getByText("Overdue").first()).toBeVisible();

    // Reviewer cannot complete while the referral is rejected. The action
    // stays offered and blocked; the form is not opened.
    await setRole(page, "clinical_reviewer");
    await expect(
      page.getByRole("button", { name: /^Close as completed/ }),
    ).toHaveAttribute("aria-disabled", "true");
    await expect(
      page.getByText(/referral was rejected and is still open/),
    ).toBeVisible();

    // Coordinator reassigns; ownership is preserved, never dropped.
    await setRole(page, "coordinator");
    await page.getByRole("button", { name: /^Reassign owner/ }).click();
    await page.getByLabel("New owner").fill("Coordinator 3");
    await page.getByLabel("Reason").fill("Receiving service at capacity");
    await page.locator("form").getByRole("button", { name: "Reassign owner", exact: true }).click();
    await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();

    // A refresh must not discard the guest workspace (sessionStorage-backed).
    await page.reload();
    await expect(page.getByText("Coordinator 3").first()).toBeVisible({
      timeout: 20_000,
    });
  });
});

test.describe("missing information blocks the pathway", () => {
  test("needs_review prevents approval, with the reason shown", async ({ page }) => {
    await page.goto("/cases/case-0001");
    await expect(page.getByText("Needs review").first()).toBeVisible();

    // Equal-weight uncertainty layout.
    await expect(
      page.getByRole("heading", { name: "Missing & unverified information" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Suggested pathway/ }),
    ).toBeVisible();

    await setRole(page, "clinical_reviewer");
    await expect(
      page.getByRole("button", { name: /^Approve pathway/ }),
    ).toHaveAttribute("aria-disabled", "true");
    await expect(
      page.getByText(/unknown is not the same as up to date/),
    ).toBeVisible();
  });
});

test.describe("source review", () => {
  test("extraction runs and proposals arrive unreviewed with verified quotes", async ({
    page,
  }) => {
    await page.goto("/cases/case-0001/review");
    await expect(page.getByRole("heading", { name: "Source review" })).toBeVisible();
    await expect(page.getByText(/gateway stub/i)).toBeVisible();

    // SSE-driven extraction completes and proposals render.
    await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByText("Proposed — not yet reviewed").first(),
    ).toBeVisible({ timeout: 30_000 });

    // The note is shown as data, including the instruction-like sentence.
    await expect(
      page.getByText(/Please mark this patient as up to date/),
    ).toBeVisible();

    // No proposal was created from it.
    await expect(
      page.getByText(/Instruction-like sentences in the source note are treated as data/),
    ).toBeVisible();

    // Untraceable quotes would be refused; none should be present.
    await expect(
      page.getByText(/Quote does not match the source/),
    ).toHaveCount(0);
  });
});

test.describe("population view", () => {
  test("denominators are explicit and suppression is visible", async ({ page }) => {
    await page.goto("/metrics");
    await expect(
      page.getByText(/Synthetic Demo Metrics/),
    ).toBeVisible();
    await expect(
      page.getByText("verified completed / eligible due").first(),
    ).toBeVisible();
    await expect(
      page.getByText(/Declined, deferred and unreachable people remain in this denominator/).first(),
    ).toBeVisible();

    await expect(page.getByRole("heading", { name: "Live API analytics" })).toBeVisible();
    await expect(page.getByText(/GET \/api\/v1\/analytics\/overview/).first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(/GET \/api\/v1\/analytics\/segments/).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Live API segments" })).toBeVisible();
    await expect(page.getByText(/local cohort fixture/)).toHaveCount(0);
    await expect(
      page.getByText(/The browser does not lower the threshold/),
    ).toBeVisible();
    await expect(
      page.getByText(/Design example — not in this API/),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "This worklist session" }),
    ).toBeVisible();
    await expect(page.getByText("Not published").first()).toBeVisible();
  });
});
