import { expect, test } from "@playwright/test";
import { setRole } from "./helpers";

// Optional isolated API target when another developer is using the default port.
function testApiUrl(url: string) {
  const target = process.env.NAMAA_E2E_API_URL;
  return target ? `${target}${new URL(url).pathname}${new URL(url).search}` : url;
}

test.beforeEach(async ({ page }) => {
  if (!process.env.NAMAA_E2E_API_URL) return;
  await page.route("**/api/v1/**", async (route) => {
    const response = await route.fetch({ url: testApiUrl(route.request().url()) });
    await route.fulfill({ response });
  });
});

const casePath = "/api/v1/cases/case-0002";

test("role changes clear case data and keep the same guest workspace", async ({ page }) => {
  const seen: { role: string; session: string; path: string }[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/cases")) {
      seen.push({ role: request.headers()["x-namaa-role"],
        session: request.headers()["x-namaa-session"], path: new URL(request.url()).pathname });
    }
  });
  await page.goto("/cases/case-0002");
  const title = page.getByRole("heading", { name: "Child B (synthetic)" });
  await expect(title).toBeVisible();
  await setRole(page, "population_analyst");
  await expect(title).toHaveCount(0);
  await expect(page.getByText("Could not load this case", { exact: true })).toBeVisible();
  await expect.poll(() => seen.some((r) => r.path === casePath && r.role === "population_analyst")).toBe(true);
  await expect.poll(() => seen.some((r) => r.path === "/api/v1/cases" && r.role === "population_analyst")).toBe(true);
  await setRole(page, "clinical_reviewer");
  await expect(title).toBeVisible();
  expect(seen.some((r) => r.path === casePath && r.role === "clinical_reviewer")).toBe(true);
  expect(new Set(seen.map((r) => r.session)).size).toBe(1);
  expect(seen.every((r) => Boolean(r.role))).toBe(true);
});

test("late responses from the previous role cannot restore case data", async ({ page }) => {
  let release!: () => void;
  let ready!: () => void;
  let settled!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const received = new Promise<void>((resolve) => { ready = resolve; });
  const completed = new Promise<void>((resolve) => { settled = resolve; });
  await page.route(`**${casePath}`, async (route) => {
    if (route.request().headers()["x-namaa-role"] !== "coordinator") {
      await route.fallback();
      return;
    }
    const response = await route.fetch({ url: testApiUrl(route.request().url()) });
    ready();
    await held;
    try {
      await route.fulfill({ response });
    } catch {
      // The role boundary aborts the obsolete read.
    } finally {
      settled();
    }
  });
  await page.goto("/cases/case-0002");
  await received;
  await setRole(page, "population_analyst");
  await expect(page.getByText("Could not load this case", { exact: true })).toBeVisible();
  release();
  await completed;
  await expect(page.getByRole("heading", { name: "Child B (synthetic)" })).toHaveCount(0);
  await expect(page.getByText("Confirm attendance after the appointment", { exact: true })).toHaveCount(0);
});

test("unreachable cases resume before booking", async ({ page }) => {
  await page.goto("/cases/case-0005");
  await expect(page.getByRole("heading", { name: "Adult E (synthetic)" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Book appointment/ })).toHaveCount(0);
  await page.getByRole("button", { name: /^Resume pathway/ }).click();
  await page.getByLabel("Reason for resuming").fill("Reached by phone-assisted support");
  await page.locator("form").getByRole("button", { name: "Resume pathway", exact: true }).click();
  await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /^Book appointment/ })).toBeVisible();
});

test("contact attempts are sent as an integer", async ({ page }) => {
  await page.goto("/cases/case-0005");
  await expect(page.getByRole("heading", { name: "Adult E (synthetic)" })).toBeVisible();
  await page.getByRole("button", { name: /^Record unreachable/ }).click();
  await page.getByLabel("Contact attempts made").fill("3");
  await page.getByRole("textbox", { name: "Detail" }).fill("No answer after three calls");
  const sent = page.waitForRequest((r) => r.url().endsWith("/case-0005/actions") && r.method() === "POST");
  await page.locator("form").getByRole("button", { name: "Record unreachable", exact: true }).click();
  expect((await sent).postDataJSON().data.attempts).toBe(3);
  await expect(page.getByText(/Recorded by the server/).first()).toBeVisible();
});
