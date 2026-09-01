import {
  test,
  expect,
  draftEmail,
  getStatus,
  ROUND_INVITATION,
  ROUND_ASSESSMENT,
  UNKNOWN_CANDIDATE_ID,
  UNKNOWN_ROUND_ID,
} from "./fixtures/email-outreach.fixture";
import { getEmailRow } from "./fixtures/db";

test.describe("Draft creation", () => {
  test("valid candidate + invitation round creates a Draft", async ({ request, candidateId }) => {
    const response = await draftEmail(request, candidateId, ROUND_INVITATION);
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body.candidate_id).toBe(candidateId);
    expect(body.status).toBe("Draft");
    expect(body.round_id).toBe(ROUND_INVITATION);
    expect(body.email_type).toBe("interview_invitation");

    // Correct round is associated on the DB row too.
    const row = await getEmailRow(candidateId);
    expect(row?.round_id).toBe(ROUND_INVITATION);
    expect(row?.status).toBe("Draft");

    // No tracking token before sending - only the placeholder draft
    // token exists (see repositories/email_repository.py::save_draft),
    // never a real one.
    expect(row?.token).toBeTruthy();
    expect(String(row?.token)).toMatch(/^draft-/);
    expect(row?.sent_at).toBeNull();
    expect(row?.message_id).toBeNull();

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Draft");
    expect(statusBody.sent_at).toBeNull();
  });

  test("draft body contains candidate/job/hr information", async ({ request, candidateId }) => {
    const response = await draftEmail(request, candidateId, ROUND_INVITATION);
    const body = await response.json();

    // testdata.json wires this candidate to JOB-001 (Senior Python
    // Developer / HR-001 Priya Sharma) via provisionCandidate().
    expect(body.body).toContain("Senior Python Developer");
    expect(body.body).toContain("Priya Sharma");
    expect(body.subject).toContain("Interview Invitation");
  });

  test("duplicate draft for the same candidate is rejected", async ({ request, candidateId }) => {
    const first = await draftEmail(request, candidateId, ROUND_INVITATION);
    expect(first.status()).toBe(200);
    const firstBody = await first.json();

    const second = await draftEmail(request, candidateId, ROUND_INVITATION);
    expect(second.status()).toBe(409);

    // Existing draft is unchanged, no duplicate row was created.
    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Draft");

    const row = await getEmailRow(candidateId);
    expect(row?.subject).toBe(firstBody.subject);
  });

  test("unknown candidate_id is rejected", async ({ request }) => {
    const response = await draftEmail(request, UNKNOWN_CANDIDATE_ID, ROUND_INVITATION);
    expect(response.status()).toBe(404);

    const body = await response.json();
    expect(body.detail).toContain(UNKNOWN_CANDIDATE_ID);
  });

  test("unknown round_id is rejected", async ({ request, candidateId }) => {
    const response = await draftEmail(request, candidateId, UNKNOWN_ROUND_ID);
    expect(response.status()).toBe(404);

    const body = await response.json();
    expect(body.detail).toContain(UNKNOWN_ROUND_ID);

    // No draft was created as a side effect of the failed attempt.
    const status = await getStatus(request, candidateId);
    expect(status.status()).toBe(404);
  });

  test("assessment round through /email/draft is rejected with 422", async ({
    request,
    candidateId,
  }) => {
    const response = await draftEmail(request, candidateId, ROUND_ASSESSMENT);
    expect(response.status()).toBe(422);

    const body = await response.json();
    expect(body.detail).toContain("assessment");
    expect(body.detail.toLowerCase()).toContain("test-round");

    // No draft was created.
    const status = await getStatus(request, candidateId);
    expect(status.status()).toBe(404);
  });
});
