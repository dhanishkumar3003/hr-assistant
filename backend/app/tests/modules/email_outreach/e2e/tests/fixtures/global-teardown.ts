import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// This file lives at backend/app/tests/modules/email_outreach/e2e/tests/fixtures/ -
// 8 levels below the repo root (where .env and infra/ live).
const REPO_ROOT = path.resolve(__dirname, "../../../../../../../..");
const ENV_PATH = path.resolve(REPO_ROOT, ".env");
const BACKUP_PATH = path.resolve(__dirname, "../../.env.e2e-backup");
const COMPOSE_DIR = path.resolve(REPO_ROOT, "infra");
const PID_FILE = path.resolve(__dirname, "../../.mock-postal-pid");
const PORT_FILE = path.resolve(__dirname, "../../.mock-postal-port");

/**
 * Undoes everything global-setup.ts did: kills the mock Postal
 * server, restores the original .env (real gmail_pubsub config), and
 * restarts the backend container back onto it.
 */
export default async function globalTeardown() {
  if (fs.existsSync(PID_FILE)) {
    const pid = Number(fs.readFileSync(PID_FILE, "utf-8").trim());
    try {
      process.kill(pid, "SIGTERM");
      console.log(`[global-teardown] Stopped mock Postal server (pid ${pid}).`);
    } catch {
      // already gone
    }
    fs.unlinkSync(PID_FILE);
  }
  if (fs.existsSync(PORT_FILE)) fs.unlinkSync(PORT_FILE);

  if (fs.existsSync(BACKUP_PATH)) {
    fs.copyFileSync(BACKUP_PATH, ENV_PATH);
    fs.unlinkSync(BACKUP_PATH);
    console.log("[global-teardown] Restored original .env.");

    console.log("[global-teardown] Restarting backend container with original config...");
    execSync("docker compose up -d --force-recreate backend", {
      cwd: COMPOSE_DIR,
      stdio: "inherit",
    });
  } else {
    console.warn("[global-teardown] No .env backup found - leaving current .env as-is.");
  }
}
