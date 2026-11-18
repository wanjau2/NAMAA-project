import { expect, test } from "@playwright/test";
import { openSessionPanel, waitForWorklist } from "./helpers";

/**
 * D3 / D6 — right-to-left layout and responsive behaviour.
 *
 * The RTL check is the one that matters most: technical strings (rule ids,
 * timestamps, revisions) must not scramble when the layout mirrors, which is
 * what `direction: ltr; unicode-bidi: isolate` on `.font-mono-tech` is for
 * (D002 §3).
 */

test("switching to Arabic mirrors the layout", async ({ page }) => {
  await page.goto("/cases");
  await waitForWorklist(page);

  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

  const scope = await openSessionPanel(page);
  await scope.getByRole("button", { name: /Arabic/ }).click();

  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  // Rendered in both the desktop row and the mobile panel; assert the visible one.
  await expect(
    scope.getByText("Unreviewed demo translation").first(),
  ).toBeVisible();
});

test("technical strings stay isolated under RTL", async ({ page }) => {
  await page.goto("/cases/case-0001");
  await expect(page.locator(".font-mono-tech").first()).toBeVisible();

  const scope = await openSessionPanel(page);
  await scope.getByRole("button", { name: /Arabic/ }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

  // Every technical string must opt out of bidi reordering.
  const styles = await page.locator(".font-mono-tech").evaluateAll((nodes) =>
    nodes.map((n) => {
      const s = getComputedStyle(n as HTMLElement);
      return { direction: s.direction, unicodeBidi: s.unicodeBidi };
    }),
  );
  expect(styles.length).toBeGreaterThan(0);
  for (const style of styles) {
    expect(style.direction).toBe("ltr");
    expect(style.unicodeBidi).toBe("isolate");
  }
});

test("no horizontal page scroll at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/", "/cases", "/cases/case-0001", "/metrics"]) {
    await page.goto(path);
    await page.waitForTimeout(800);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `${path} should not scroll horizontally`).toBeLessThanOrEqual(1);
  }
});

test("the simulation bar collapses below 640px and still shows the notice", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/cases");

  await expect(
    page.getByText("SYNTHETIC DEMO DATA", { exact: true }),
  ).toBeVisible();
  const toggle = page.getByRole("button", { name: "Session" });
  await expect(toggle).toBeVisible();

  await toggle.click();
  await expect(
    page.locator("#sim-bar-mobile-panel").getByLabel("Simulated role"),
  ).toBeVisible();
});
