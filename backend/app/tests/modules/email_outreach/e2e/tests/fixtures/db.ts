import { Pool } from "pg";

/**
 * Test-only direct DB access. The email_outreach API never exposes
 * the tracking token (email_outreach_emails.token) - it's only used
 * internally for subject-line/Message-ID reply matching (see
 * services/reply_matcher.py) - so tests that need it (to simulate a
 * reply via POST /email/webhook/reply, or to manipulate
 * response_due_at for the threshold job) read it directly. This
 * mirrors the prompt's own allowance: "Database -> only when
 * necessary" for deterministic setup, never as a substitute for
 * exercising the real API under test.
 *
 * Credentials match infra/docker-compose.yml's postgres service
 * (hr_user/hr_pass on localhost:5432, exposed to the host).
 */
const pool = new Pool({
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT || 5432),
  user: process.env.DB_USER || "hr_user",
  password: process.env.DB_PASSWORD || "hr_pass",
  database: process.env.DB_NAME || "hr_assistant_poc",
});

export async function getTokenForCandidate(candidateId: string): Promise<string | null> {
  const result = await pool.query(
    `SELECT token FROM email_outreach_emails
     WHERE candidate_id = $1
     ORDER BY created_at DESC LIMIT 1`,
    [candidateId]
  );
  return result.rows[0]?.token ?? null;
}

export async function getEmailRow(candidateId: string): Promise<Record<string, unknown> | null> {
  const result = await pool.query(
    `SELECT * FROM email_outreach_emails
     WHERE candidate_id = $1
     ORDER BY created_at DESC LIMIT 1`,
    [candidateId]
  );
  return result.rows[0] ?? null;
}

/**
 * Backdates a Sent candidate's response_due_at so the threshold job
 * (POST /email/threshold/run) has something past-due to act on,
 * without waiting the real 72-hour default. Only ever used on rows
 * created by these tests (candidateId comes from provisionCandidate()),
 * never on real data.
 */
export async function backdateResponseDeadline(candidateId: string, hoursAgo: number): Promise<void> {
  await pool.query(
    `UPDATE email_outreach_emails
     SET response_due_at = NOW() - ($2 || ' hours')::interval
     WHERE candidate_id = $1`,
    [candidateId, hoursAgo]
  );
}

export async function getMessageId(candidateId: string): Promise<string | null> {
  const result = await pool.query(
    `SELECT message_id FROM email_outreach_emails
     WHERE candidate_id = $1
     ORDER BY created_at DESC LIMIT 1`,
    [candidateId]
  );
  return result.rows[0]?.message_id ?? null;
}

export async function closeDbPool(): Promise<void> {
  await pool.end();
}
