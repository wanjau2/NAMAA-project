import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { setRole, waitForWorklist } from "./helpers";

/**
 * D4 / D5 — keyboard operability and automated accessibility.
 *
 * The work plan's definition of done requires every control to be keyboard
 * accessible. That includes the role-gated controls, which are `aria-disabled`
 * rather than `disabled` precisely so their explanation stays reachable
 * (D002 §2) — if that ever regresses to a native `disabled`, these fail.
 */

const PAGES = [
  { path: "/", name: "guest entry" },
  { path: "/cases", name: "worklist" },
  { path: "/cases/case-0001", name: "case detail" },
  { path: "/metrics", name: "population view" },
];

for (const target of PAGES) {
  test(`axe: ${target.name} has no critical or serious violations`, async ({ page }) => {
    await page.goto(target.path);
    if (target.path === "/cases") await waitForWorklist(page);
    await page.waitForTimeout(1500); // let client data settle

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const blocking = results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact ?? ""),
    );
    if (blocking.length > 0) {
      console.log(
        `axe violations on ${target.path}:\n` +
          blocking
            .map(
              (v) =>
                `  [${v.impact}] ${v.id}: ${v.help}\n    ${v.nodes
                  .slice(0, 3)
                  .map((n) => n.target.join(" "))
                  .join("\n    ")}`,
            )
            .join("\n"),
      );
    }
    expect(blocking.map((v) => `${v.impact}: ${v.id}`)).toEqual([]);
  });
}

test("a role-gated control stays focusable and announces its reason", async ({ page }) => {
  await page.goto("/cases/case-0002");
  await setRole(page, "coordinator");

  // A clinical-reviewer action that IS offered at this stage, so the panel
  // renders it in the gated state rather than omitting it.
  const gated = page.getByRole("button", { name: /^Close for another reason/ });
  await expect(gated).toHaveAttribute("aria-disabled", "true");

  // Native `disabled` would remove it from the focus order. aria-disabled must not.
  await gated.focus();
  await expect(gated).toBeFocused();

  const describedBy = await gated.getAttribute("aria-describedby");
  expect(describedBy).toBeTruthy();
  await expect(page.locator(`#${describedBy}`)).toBeVisible();
  await expect(page.locator(`#${describedBy}`)).toContainText(
    /Requires the Clinical Reviewer role/,
  );
});

test("the worklist is operable by keyboard alone", async ({ page }) => {
  await page.goto("/cases");
  await waitForWorklist(page);

  // Tab until a case link takes focus, then activate it with the keyboard.
  let reached = false;
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      return el ? `${el.tagName}:${(el.textContent ?? "").trim().slice(0, 40)}` : "";
    });
    if (focused.startsWith("A:") && focused.includes("(synthetic)")) {
      reached = true;
      break;
    }
  }
  expect(reached, "a case link should be reachable by Tab").toBe(true);

  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/cases\/case-/);
});

test("focus is visible on interactive controls", async ({ page }) => {
  await page.goto("/cases");
  await waitForWorklist(page);
  await page.keyboard.press("Tab");

  const outline = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const style = getComputedStyle(el);
    return { width: style.outlineWidth, style: style.outlineStyle };
  });
  expect(outline).not.toBeNull();
  expect(outline!.style).not.toBe("none");
  expect(parseFloat(outline!.width)).toBeGreaterThanOrEqual(1);
});
