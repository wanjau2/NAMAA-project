import { expect, test, type Page } from "@playwright/test";

/**
 * M07 — extraction recovery and terminal-state handling.
 *
 * A still-running, failed, cancelled or timed-out job must never be shown as
 * extraction-empty just because it has no proposals yet.
 */

const PROPOSAL = {
  id: "prop-recovery-1",
  version: 1,
  state: "proposed",
  source_document_id: "doc-synthetic-11",
  source_document_version: "1",
  source_sha256: "abc",
  fact: {
    concept: "Last well-child visit",
    value_text: "Caregiver cannot recall the date",
    subject: "patient",
    assertion: "uncertain",
    effective_date: null,
    excerpt: "cannot recall the date",
    proposed_resource_type: "Observation",
    relationship: null,
  },
  offset_start: null,
  offset_end: null,
  offset_unit: "unicode_code_points",
  issues: [],
  model: {
    model_id: "offline",
    model_revision: "offline-fixture-v1",
    prompt_version: "v1",
    simulated: true,
  },
};

function jobPayload(state: string, extra: Record<string, unknown> = {}) {
  return {
    job_id: "job-recovery",
    document_id: "doc-synthetic-11",
    document_version: 1,
    state,
    progress_percent: state === "succeeded" ? 100 : 40,
    message: state,
    elapsed_ms: 12_000,
    timeout_ms: 90_000,
    model_revision: "offline-fixture-v1",
    prompt_version: "v1",
    error_code: state === "succeeded" ? null : state,
    error_message: state === "succeeded" ? null : state,
    synthetic: true,
    inference_mode: "offline_fixture",
    proposals: [],
    ...extra,
  };
}

function sseFrame(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

async function mockExtraction(
  page: Page,
  opts: {
    sseBody: string;
    status: Record<string, unknown> | (() => Record<string, unknown>);
  },
) {
  await page.route("**/api/v1/extractions/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/events")) {
      await route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
          "access-control-allow-origin": "*",
        },
        body: opts.sseBody,
      });
      return;
    }
    const payload =
      typeof opts.status === "function" ? opts.status() : opts.status;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });
}

test("a timed-out extraction is not an empty success", async ({ page }) => {
  const terminal = jobPayload("timed_out");
  await mockExtraction(page, {
    sseBody: sseFrame("terminal", { event: "terminal", ...terminal }),
    status: terminal,
  });
  await page.goto("/cases/case-0001/review");
  await expect(page.getByText("Extraction timed out")).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/not.*finding of no care gap/i).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Extraction succeeded and proposed nothing/),
  ).toHaveCount(0);
});

test("a failed extraction is not an empty success", async ({ page }) => {
  const terminal = jobPayload("failed");
  await mockExtraction(page, {
    sseBody: sseFrame("terminal", { event: "terminal", ...terminal }),
    status: terminal,
  });
  await page.goto("/cases/case-0001/review");
  await expect(page.getByText("Extraction did not complete")).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/Extraction succeeded and proposed nothing/),
  ).toHaveCount(0);
});

test("a cancelled extraction is distinct from failure and from empty", async ({
  page,
}) => {
  const terminal = jobPayload("cancelled");
  await mockExtraction(page, {
    sseBody: sseFrame("terminal", { event: "terminal", ...terminal }),
    status: terminal,
  });
  await page.goto("/cases/case-0001/review");
  await expect(page.getByText("Extraction was cancelled")).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/Extraction succeeded and proposed nothing/),
  ).toHaveCount(0);
});

test("only a succeeded job with zero proposals is extraction-empty", async ({
  page,
}) => {
  const terminal = jobPayload("succeeded", { proposals: [] });
  await mockExtraction(page, {
    sseBody: sseFrame("terminal", {
      event: "terminal",
      ...terminal,
      proposals: [],
    }),
    status: terminal,
  });
  await page.goto("/cases/case-0001/review");
  await expect(
    page.getByText(/Extraction succeeded and proposed nothing/),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Extraction timed out")).toHaveCount(0);
  await expect(page.getByText("Extraction did not complete")).toHaveCount(0);
});

test("a stream drop while running recovers via status GET, not empty", async ({
  page,
}) => {
  let polls = 0;
  const running = jobPayload("running", {
    error_code: null,
    error_message: null,
  });
  await mockExtraction(page, {
    sseBody: sseFrame("progress", { event: "progress", ...running }),
    status: () => {
      polls += 1;
      if (polls < 2) return running;
      return jobPayload("succeeded", { proposals: [PROPOSAL] });
    },
  });
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Last well-child visit").first()).toBeVisible();
  await expect(
    page.getByText(/Extraction succeeded and proposed nothing/),
  ).toHaveCount(0);
});

test("malformed frames recover from status GET", async ({ page }) => {
  const succeeded = jobPayload("succeeded", { proposals: [PROPOSAL] });
  await mockExtraction(page, {
    sseBody: "event: progress\ndata: {not-json\n\n",
    status: succeeded,
  });
  await page.goto("/cases/case-0001/review");
  await expect(page.getByRole("heading", { name: /Proposed facts/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Last well-child visit").first()).toBeVisible();
});
