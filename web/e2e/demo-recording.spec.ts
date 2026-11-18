import { expect, test } from "@playwright/test";
import { openSessionPanel, setRole, waitForWorklist } from "./helpers";

/**
 * E3 / E4 — demonstration recording and deck screenshots.
 *
 * Walks the product in the order of the work plan's three-minute sequence, with
 * deliberate pauses so the video is watchable and each screenshot lands on a
 * settled screen. Narration is the presenters' job; this is the footage.
 *
 * Everything shown is synthetic. No credentials appear at any point.
 *
 * Output:
 *   docs/03-evidence/E-delivery/screenshots/NN-name.png
 *   docs/03-evidence/E-delivery/recording/   (Playwright video)
 */

const SHOTS = "../docs/03-evidence/E-delivery/screenshots";

/** Pause long enough to read the screen in the recording. */
async function beat(page: import("@playwright/test").Page, ms = 1800) {
  await page.waitForTimeout(ms);
}

async function shot(
  page: import("@playwright/test").Page,
  name: string,
  fullPage = false,
) {
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage });
}

test("demonstration walkthrough", async ({ page }) => {
  // ---------------------------------------------------------------- 1. Entry
  await page.goto("/");
  await expect(page.getByTestId("sim-notice")).toBeVisible();
  await beat(page);
  await shot(page, "01-guest-entry");

  await page.getByRole("link", { name: /Start Synthetic Demo Session/ }).click();
  await waitForWorklist(page);
  await beat(page);
  await shot(page, "02-worklist");

  // Overdue filter: escalated work is never hidden.
  await page.getByRole("button", { name: "Overdue only" }).click();
  await beat(page, 1500);
  await shot(page, "03-worklist-overdue");
  await page.getByRole("button", { name: "Overdue only" }).click();
  await beat(page, 800);

  // ------------------------------------------------- 2. Child: uncertainty
  await page.goto("/cases/case-0001");
  await expect(page.getByText("Needs review").first()).toBeVisible();
  await beat(page);
  await shot(page, "04-child-uncertainty", true);

  // Approval is blocked while information is missing.
  await setRole(page, "clinical_reviewer");
  await page.getByRole("button", { name: /^Approve pathway/ }).click();
  await page.getByLabel(/I have reviewed the contributing records/).check();
  await page
    .locator("form")
    .getByRole("button", { name: "Approve pathway", exact: true })
    .click();
  await expect(
    page.getByText(/unknown is not the same as up to date/),
  ).toBeVisible();
  await beat(page, 2500);
  await shot(page, "05-approval-blocked");

  // ------------------------------------------------ 3. Source review + SSE
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText("Proposed — not yet reviewed").first(),
  ).toBeVisible({ timeout: 30_000 });
  await beat(page, 2200);
  await shot(page, "06-source-review", true);

  // Hovering a proposal highlights its exact excerpt in the note.
  await page.getByText("Last well-child visit").first().hover();
  await beat(page, 1800);
  await shot(page, "07-excerpt-highlighted");

  // ------------------------------------- 4. Child journey: evidence closure
  await page.goto("/cases/case-0002");
  await expect(page.getByRole("heading", { name: "Child B (synthetic)" })).toBeVisible();
  await beat(page, 1200);

  await setRole(page, "coordinator");
  await page.getByRole("button", { name: /^Record attendance/ }).click();
  await page.getByLabel("Outcome").selectOption("attended");
  await beat(page, 1200);
  await page
    .locator("form")
    .getByRole("button", { name: "Record attendance", exact: true })
    .click();
  await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
  await beat(page, 2000);
  await shot(page, "08-attendance-recorded");

  // Closure belongs to the clinical reviewer; the boundary is shown, not hidden.
  const close = page.getByRole("button", { name: /^Close as completed/ });
  await expect(close).toHaveAttribute("aria-disabled", "true");
  // Close-up of the action panel: the gated control is visible with its reason
  // rather than hidden. (A programmatic focus() does not trigger :focus-visible
  // in Chromium, so a full-page shot would be indistinguishable from the last.)
  await close.scrollIntoViewIfNeeded();
  await beat(page, 1500);
  await page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Actions" }) })
    .screenshot({ path: `${SHOTS}/09-role-boundary.png` });

  await setRole(page, "clinical_reviewer");
  await close.click();
  await page.getByLabel(/I authorize closure/).check();
  await beat(page, 1000);
  // Evidence is required: submit without it first.
  await page
    .locator("form")
    .getByRole("button", { name: "Close as completed", exact: true })
    .click();
  await expect(page.getByText("This field is required.")).toBeVisible();
  await beat(page, 2200);
  await shot(page, "10-evidence-required");

  await page.getByLabel("Evidence reference").fill("Encounter/enc-synthetic-02");
  await beat(page, 900);
  await page
    .locator("form")
    .getByRole("button", { name: "Close as completed", exact: true })
    .click();
  await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
  await beat(page, 2200);
  await shot(page, "11-completed-with-evidence", true);

  // ----------------------------------------- 5. Adult: referral and handoff
  await page.goto("/cases/case-0003");
  await expect(page.getByText("Overdue").first()).toBeVisible();
  await beat(page, 1500);
  await shot(page, "12-adult-overdue", true);

  await setRole(page, "clinical_reviewer");
  await page.getByRole("button", { name: /^Close as completed/ }).click();
  await page.getByLabel("Evidence reference").fill("Procedure/proc-synthetic-03");
  await page.getByLabel(/I authorize closure/).check();
  await page
    .locator("form")
    .getByRole("button", { name: "Close as completed", exact: true })
    .click();
  await expect(
    page.getByText(/referral was rejected and is still open/),
  ).toBeVisible();
  await beat(page, 2500);
  await shot(page, "13-rejected-referral-blocks-closure");

  await setRole(page, "coordinator");
  await page.getByRole("button", { name: /^Reassign owner/ }).click();
  await page.getByLabel("New owner").fill("Coordinator 3");
  await page.getByLabel("Reason").fill("Receiving service at capacity");
  await beat(page, 1200);
  await page
    .locator("form")
    .getByRole("button", { name: "Reassign owner", exact: true })
    .click();
  await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
  await beat(page, 2000);
  await shot(page, "14-reassigned");

  // ------------------------------------------------ 6. Population and limits
  await page.goto("/metrics");
  await expect(page.getByText(/Synthetic Demo Metrics/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Live API analytics" })).toBeVisible();
  await expect(page.getByText(/cells suppressed/).first()).toBeVisible({
    timeout: 20_000,
  });
  await beat(page, 2200);
  await shot(page, "15-metrics-live-api");

  await page.mouse.wheel(0, 900);
  await beat(page, 1800);
  await shot(page, "16-metrics-denominators");

  await page.mouse.wheel(0, 1400);
  await beat(page, 1800);
  await shot(page, "17-metrics-suppression");

  // ------------------------------------------------------- 7. Bilingual/RTL
  await page.goto("/cases/case-0001");
  const scope = await openSessionPanel(page);
  await scope.getByRole("button", { name: /Arabic/ }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await beat(page, 2500);
  await shot(page, "18-rtl-mirrored", true);
});
