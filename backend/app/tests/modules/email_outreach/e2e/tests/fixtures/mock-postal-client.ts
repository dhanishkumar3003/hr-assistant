import fs from "node:fs";
import path from "node:path";
import type { CapturedSend } from "./mock-postal-server";

const PORT_FILE = path.resolve(__dirname, "../../.mock-postal-port");

function getMockPort(): number {
  return Number(fs.readFileSync(PORT_FILE, "utf-8").trim());
}

/** Reads all sends the mock Postal server has captured so far, from a test worker process. */
export async function getCapturedSends(): Promise<CapturedSend[]> {
  const res = await fetch(`http://localhost:${getMockPort()}/__captured`);
  return res.json();
}

export async function getLastSendTo(recipient: string): Promise<CapturedSend | undefined> {
  const all = await getCapturedSends();
  return [...all].reverse().find((c) => c.to.includes(recipient));
}

export async function clearCapturedSends(): Promise<void> {
  await fetch(`http://localhost:${getMockPort()}/__clear`, { method: "POST" });
}
