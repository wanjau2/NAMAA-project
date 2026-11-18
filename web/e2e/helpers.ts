import { expect, type Page } from "@playwright/test";

/** Switch the simulated role in the persistent simulation bar. */
export async function setRole(
  page: Page,
  role: "coordinator" | "clinical_reviewer" | "population_analyst",
) {
  // Under 640px the controls collapse behind a "Session" toggle (D002 §9).
  const panel = await openSessionPanel(page);
  await panel.getByLabel("Simulated role").selectOption(role);
}

/** Wait for the worklist to finish loading from the API. */
export async function waitForWorklist(page: Page) {
  await expect(page.getByRole("heading", { name: "Coordinator worklist" })).toBeVisible();
  await expect(page.getByText("Loading synthetic cases…")).toBeHidden({
    timeout: 20_000,
  });
}

/** Open an action in the case-detail action panel and fill it in. */
export async function openAction(page: Page, label: string) {
  const button = page.getByRole("button", { name: new RegExp(`^${label}`) });
  await expect(button).toBeVisible();
  await button.click();
}

export async function expectApiConnected(page: Page) {
  // The chip collapses to a dot below 640px; its accessible name carries the state.
  await expect(
    page.getByRole("status", { name: "API connected" }),
  ).toBeAttached({ timeout: 20_000 });
}

/**
 * Open the collapsed session panel when the viewport is below 640px.
 * Idempotent: a second call must not toggle the panel shut again.
 */
export async function openSessionPanel(page: Page) {
  const toggle = page.getByRole("button", { name: "Session" });
  if (!(await toggle.isVisible().catch(() => false))) {
    return page.locator("body");
  }
  if ((await toggle.getAttribute("aria-expanded")) !== "true") {
    await toggle.click();
  }
  const panel = page.locator("#sim-bar-mobile-panel");
  await panel.waitFor({ state: "visible" });
  return panel;
}
