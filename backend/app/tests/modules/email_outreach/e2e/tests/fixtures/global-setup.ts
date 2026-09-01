import { execSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// This file lives at backend/app/tests/modules/email_outreach/e2e/tests/fixtures/ -
// 8 levels below the repo root (where .env and infra/ live).
const REPO_ROOT = path.resolve(__dirname, "../../../../../../../..");
const ENV_PATH = path.resolve(REPO_ROOT, ".env");
const BACKUP_PATH = path.resolve(__dirname, "../../.env.e2e-backup");
const COMPOSE_DIR = path.resolve(REPO_ROOT, "infra");
const PORT_FILE = path.resolve(__dirname, "../../.mock-postal-port");
const PID_FILE = path.resolve(__dirname, "../../.mock-postal-pid");

/**
 * Points the live backend at a local mock Postal server for the
 * duration of the suite, so /email/send actually transitions to Sent
 * (real state-machine coverage) without any real email leaving the
 * machine - the currently-configured gmail_pubsub backend would hit
 * the real Gmail API otherwise. Backs up .env and restores it (plus
 * restarts the container back to its prior config) in global-teardown.ts.
 *
 * The mock server runs as a detached child process (see
 * mock-postal-standalone.ts) rather than in this script's own process,
 * since globalSetup exits after returning - an in-process HTTP server
 * would die with it before any test ran.
 */
export default async function globalSetup() {
  const port = await startMockServer();
  console.log(`[global-setup] Mock Postal server listening on port ${port}`);

  const original = fs.readFileSync(ENV_PATH, "utf-8");
  fs.writeFileSync(BACKUP_PATH, original, "utf-8");

  const updated = original
    .replace(/^EMAIL_BACKEND=.*$/m, "EMAIL_BACKEND=postal")
    .replace(
      /^POSTAL_API_URL=.*$/m,
      `POSTAL_API_URL=http://host.docker.internal:${port}/api/v1/send/message`
    )
    .replace(/^POSTAL_API_KEY=.*$/m, "POSTAL_API_KEY=e2e-test-key")
    .replace(/^POSTAL_SENDER_ADDRESS=.*$/m, "POSTAL_SENDER_ADDRESS=e2e-sender@example.com");
  fs.writeFileSync(ENV_PATH, updated, "utf-8");

  console.log("[global-setup] Restarting backend container with EMAIL_BACKEND=postal...");
  execSync("docker compose up -d --force-recreate backend", {
    cwd: COMPOSE_DIR,
    stdio: "inherit",
  });

  await waitForBackend();
  console.log("[global-setup] Backend ready.");
}

function startMockServer(): Promise<number> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      ["-r", "ts-node/register", path.resolve(__dirname, "mock-postal-standalone.ts")],
      { detached: true, stdio: ["ignore", "pipe", "inherit"] }
    );

    let resolved = false;
    child.stdout.on("data", (chunk: Buffer) => {
      const match = chunk.toString().match(/PORT=(\d+)/);
      if (match && !resolved) {
        resolved = true;
        const port = Number(match[1]);
        fs.writeFileSync(PORT_FILE, String(port), "utf-8");
        fs.writeFileSync(PID_FILE, String(child.pid), "utf-8");
        child.unref();
        resolve(port);
      }
    });

    child.on("error", reject);
    setTimeout(() => {
      if (!resolved) reject(new Error("Mock Postal server did not report a port within 10s"));
    }, 10_000);
  });
}

async function waitForBackend(timeoutMs = 180_000): Promise<void> {
  const baseUrl = process.env.BACKEND_BASE_URL || "http://localhost:8000";
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${baseUrl}/email/ping`);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Backend did not become ready within timeout after container restart");
}
