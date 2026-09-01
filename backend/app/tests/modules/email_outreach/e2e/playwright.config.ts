import { defineConfig, devices } from "@playwright/test";

/**
 * API-level E2E suite for the email_outreach backend module.
 *
 * There is no frontend UI for this module (checked - the Next.js app
 * only has a landing page, /login, and the candidate voice-interview
 * flow; no dashboard, draft/approve/send screens, or status/history
 * views exist). These tests drive the real HTTP API via Playwright's
 * `request` fixture instead of a browser, since there is no UI to
 * click through - see README.md in this directory for the full
 * discrepancy report.
 */
export default defineConfig({
  testDir: "./tests",
  globalSetup: require.resolve("./tests/fixtures/global-setup.ts"),
  globalTeardown: require.resolve("./tests/fixtures/global-teardown.ts"),
  fullyParallel: false, // shared Postgres + testdata.json state - avoid cross-test races
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  // Several endpoints (webhook/reply, draft's rejection round) fall
  // through to a real Ollama LLM call (see llm_reply_classifier.py) -
  // generous timeout so a slow/cold model load doesn't flake tests.
  timeout: 60_000,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: process.env.BACKEND_BASE_URL || "http://localhost:8000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    extraHTTPHeaders: {
      "Content-Type": "application/json",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
