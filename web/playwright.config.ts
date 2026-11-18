import { defineConfig, devices } from "@playwright/test";

/**
 * Browser verification for the Namaa demo (roadmap D3–D6, E1–E2).
 *
 * Starts both services so a run is reproducible from a clean checkout:
 * the API on :8000 and the production Next build on :3200. Everything below
 * exercises synthetic data only.
 */
const WEB_PORT = 3200;
const API_PORT = 8000;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // the demo API holds one SQLite workspace per session
  workers: 1,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "desktop",
      testIgnore: /demo-recording\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      testIgnore: /demo-recording\.spec\.ts/,
      use: { ...devices["Pixel 7"] },
    },
    {
      // E3/E4: the demonstration recording and the screenshots for the deck.
      // Run on its own: `npm run demo`.
      name: "demo",
      testMatch: /demo-recording\.spec\.ts/,
      timeout: 240_000,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        video: { mode: "on", size: { width: 1440, height: 900 } },
      },
    },
  ],

  webServer: [
    {
      // The API's CORS allowlist defaults to port 3000 only. The browser origin
      // here is :3200, so it must be allowed explicitly or every fetch is
      // blocked and the UI correctly reports "API unreachable".
      command:
        `cd ../api && NAMAA_CORS_ORIGINS=http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT} ` +
        `./.venv/bin/uvicorn app.main:app --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: `npx next start -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
