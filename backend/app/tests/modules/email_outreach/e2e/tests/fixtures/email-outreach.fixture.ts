import { test as base, expect, APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

/**
 * Path to the live testdata.json the backend container reads from
 * (bind-mounted, so edits here take effect on the next API call - no
 * restart needed; see candidate_source.py::_load, which re-reads the
 * file on every call rather than caching it). It's the pytest suite's
 * fixture file too, one directory up from this e2e/ subfolder.
 */
const TESTDATA_PATH = path.resolve(__dirname, "../../../testdata.json");

const KNOWN_JOB_ID = "JOB-001";
const KNOWN_HR_ID = "HR-001";
export const ROUND_INVITATION = "ROUND-1";
export const ROUND_ASSESSMENT = "ROUND-2-BACKEND";
export const ROUND_NEXT = "ROUND-3";
export const ROUND_REJECTED = "ROUND-REJECTED";
export const HR_ID = KNOWN_HR_ID;
export const UNKNOWN_CANDIDATE_ID = "E2E-DOES-NOT-EXIST";
export const UNKNOWN_ROUND_ID = "ROUND-DOES-NOT-EXIST";
export const UNKNOWN_HR_ID = "HR-DOES-NOT-EXIST";

interface TestData {
  candidates: Array<Record<string, unknown>>;
  jobs: Array<Record<string, unknown>>;
  hrs: Array<Record<string, unknown>>;
  rounds: Array<Record<string, unknown>>;
}

function readTestData(): TestData {
  const raw = fs.readFileSync(TESTDATA_PATH, "utf-8");
  return JSON.parse(raw);
}

function writeTestData(data: TestData): void {
  fs.writeFileSync(TESTDATA_PATH, JSON.stringify(data, null, 2) + "\n", "utf-8");
}

/**
 * Appends a fresh, uniquely-id'd candidate to testdata.json, wired to
 * an existing job/hr record already in the catalog. Returns the new
 * candidate_id. Caller is responsible for calling removeCandidate()
 * in teardown (the fixture below does this automatically).
 */
export function provisionCandidate(namePrefix = "E2E"): string {
  const candidateId = `${namePrefix}-${Date.now()}-${crypto.randomBytes(3).toString("hex")}`;
  const data = readTestData();

  data.candidates.push({
    candidate_id: candidateId,
    name: `${namePrefix} Test Candidate`,
    email: "e2e-test-candidate@example.com",
    phone: "+91-9000000000",
    location: "Chennai, Tamil Nadu, India",
    experience: "3 years",
    skills: ["Python"],
    current_designation: "Backend Developer",
    current_company: "E2E Test Co",
    education: "B.Tech in Computer Science",
    job_id: KNOWN_JOB_ID,
    hr_id: KNOWN_HR_ID,
  });

  writeTestData(data);
  return candidateId;
}

export function removeCandidate(candidateId: string): void {
  const data = readTestData();
  data.candidates = data.candidates.filter((c) => c.candidate_id !== candidateId);
  writeTestData(data);
}

type Fixtures = {
  /** A freshly provisioned, unused candidate_id - removed from testdata.json after the test. */
  candidateId: string;
  /** Second independent candidate, for tests needing two at once (e.g. duplicate-draft checks against separate subjects). */
  secondCandidateId: string;
};

export const test = base.extend<Fixtures>({
  candidateId: async ({}, use) => {
    const id = provisionCandidate();
    await use(id);
    removeCandidate(id);
  },
  secondCandidateId: async ({}, use) => {
    const id = provisionCandidate("E2E2");
    await use(id);
    removeCandidate(id);
  },
});

export { expect };

/** Draft a candidate for a given round; returns the parsed response body. */
export async function draftEmail(
  request: APIRequestContext,
  candidateId: string,
  roundId = ROUND_INVITATION
) {
  const response = await request.post("/email/draft", {
    data: { candidate_id: candidateId, round_id: roundId },
  });
  return response;
}

export async function approveDraft(
  request: APIRequestContext,
  candidateId: string,
  opts: { approvedByHrId?: string; editedBody?: string } = {}
) {
  const body: Record<string, unknown> = { candidate_id: candidateId };
  if (opts.approvedByHrId !== undefined) body.approved_by_hr_id = opts.approvedByHrId;
  if (opts.editedBody !== undefined) body.edited_body = opts.editedBody;
  return request.post("/email/approve", { data: body });
}

export async function rejectDraft(request: APIRequestContext, candidateId: string) {
  return request.post("/email/reject", { data: { candidate_id: candidateId } });
}

export async function sendEmail(request: APIRequestContext, candidateId: string) {
  return request.post("/email/send", { data: { candidate_id: candidateId } });
}

export async function getStatus(request: APIRequestContext, candidateId: string) {
  return request.get(`/email/status/${encodeURIComponent(candidateId)}`);
}

export async function getHistory(request: APIRequestContext, candidateId: string) {
  return request.get(`/email/status/${encodeURIComponent(candidateId)}/history`);
}

export async function sendWebhookReply(
  request: APIRequestContext,
  token: string,
  body: string,
  subject = "Re: Interview Invitation"
) {
  return request.post("/email/webhook/reply", {
    data: { token, subject, body },
  });
}

export async function runTestRound(
  request: APIRequestContext,
  candidateId: string,
  roundId: string,
  url: string
) {
  return request.post("/email/test-round", {
    data: { candidate_id: candidateId, round_id: roundId, url },
  });
}

export async function runThreshold(request: APIRequestContext) {
  return request.post("/email/threshold/run");
}

/**
 * Full draft -> approve -> send happy path, returning the tracking
 * token pulled from status (the API never echoes the token directly -
 * it's only visible in email_outreach_emails.token, which status/
 * history don't expose either - see "Remaining limitations" in
 * README.md for how tests resolve a token to test replies).
 */
export async function draftApproveSend(
  request: APIRequestContext,
  candidateId: string,
  roundId = ROUND_INVITATION
) {
  const draft = await draftEmail(request, candidateId, roundId);
  expect(draft.ok(), `draft failed: ${await draft.text()}`).toBeTruthy();

  const approve = await approveDraft(request, candidateId, { approvedByHrId: HR_ID });
  expect(approve.ok(), `approve failed: ${await approve.text()}`).toBeTruthy();

  const send = await sendEmail(request, candidateId);
  expect(send.ok(), `send failed: ${await send.text()}`).toBeTruthy();

  return { draft, approve, send };
}
