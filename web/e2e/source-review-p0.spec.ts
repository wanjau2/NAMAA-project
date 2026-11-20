import { expect, test } from "@playwright/test";
import { setRole } from "./helpers";

test("case detail shows caregiver authority from the API, never a hardcoded verified label", async ({
  page,
}) => {
  await page.goto("/cases/case-0001");
  await expect(page.getByRole("heading", { name: "Child A (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Verified caregiver (synthetic record)")).toBeVisible();
  await expect(page.getByText("Verified (synthetic)", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText(/Caregiver relationship is not authorization/),
  ).toBeVisible();

  await page.goto("/cases/case-0003");
  await expect(page.getByRole("heading", { name: "Adult C (synthetic)" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Self — no caregiver required")).toBeVisible();
  await expect(page.getByText("Verified (synthetic)", { exact: true })).toHaveCount(0);
});

test("accept and correct persist nested facts without inventing acknowledgements", async ({
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

  const first = page.locator("article").nth(0);
  await expect(first.getByRole("button", { name: "Accept" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );

  for (const box of await first.getByRole("checkbox").all()) {
    await box.check();
  }
  await first.getByRole("button", { name: "Accept" }).click();
  await expect(first.getByText(/Recorded in this synthetic workspace/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(first.getByText(/Accepted by reviewer/)).toBeVisible();
  await expect(first.getByText(/Practitioner\/demo-reviewer/).first()).toBeVisible();

  const second = page.locator("article").nth(1);
  for (const box of await second.getByRole("checkbox").all()) {
    await box.check();
  }
  await second.getByRole("button", { name: "Correct" }).click();
  const statement = second.getByLabel("Statement");
  const original = await statement.inputValue();
  await statement.fill("cannot recall the date");
  await second.getByLabel("Reason for the correction").fill(
    "Shortened to the quoted uncertainty.",
  );
  const sent = page.waitForRequest(
    (request) =>
      request.url().includes("/facts/") &&
      request.url().endsWith("/review") &&
      request.method() === "POST",
  );
  await second.getByRole("button", { name: "Save correction" }).click();
  const body = (await sent).postDataJSON() as {
    action: string;
    correction: { value_text: string } | null;
    acknowledged_issues: string[];
    reviewer_reference?: string;
  };
  expect(body.action).toBe("correct");
  expect(body.correction?.value_text).toBe("cannot recall the date");
  expect(body.reviewer_reference).toBeUndefined();
  expect(body.acknowledged_issues.length).toBeGreaterThan(0);
  expect(original).not.toBe("cannot recall the date");
  await expect(second.getByText(/Recorded in this synthetic workspace/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(second.getByText(/Corrected and accepted/)).toBeVisible();
});
