import {
  test,
  expect,
  runTestRound,
  draftApproveSend,
  getStatus,
  ROUND_INVITATION,
  ROUND_ASSESSMENT,
  UNKNOWN_CANDIDATE_ID,
  UNKNOWN_ROUND_ID,
} from "./fixtures/email-outreach.fixture";
import { getEmailRow } from "./fixtures/db";
import { getLastSendTo } from "./fixtures/mock-postal-client";

const TEST_URL = "https://assess.example.com/t/e2e-test";
const CANDIDATE_EMAIL = "e2e-test-candidate@example.com";

test.describe("Assessment / test-round", () => {
  test("sending an assessment round updates round tracking without going through draft/approve", async ({
    request,
    candidateId,
  }) => {
    // test-round sends against an EXISTING Sent row (see
    // services/test_round_service.py) - it does not create a new one,
    // so the candidate must already have gone through the normal
    // invitation flow first.
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const rowBeforeAssessment = await getEmailRow(candidateId);
    expect(rowBeforeAssessment?.round_id).toBe(ROUND_INVITATION);
    expect(rowBeforeAssessment?.round_number).toBeNull(); // invitation is an acceptance gate, not a numbered round

    const response = await runTestRound(request, candidateId, ROUND_ASSESSMENT, TEST_URL);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("sent");

    // Candidate's current round advanced - no new Email row was
    // created (still one row, now updated).
    const rowAfter = await getEmailRow(candidateId);
    expect(rowAfter?.round_id).toBe(ROUND_ASSESSMENT);
    expect(rowAfter?.round_number).toBe(1);
    expect(rowAfter?.email_id).toBe(rowBeforeAssessment?.email_id);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.round_id).toBe(ROUND_ASSESSMENT);
    expect(statusBody.round_number).toBe(1);

    // The assessment link was actually emailed. Unlike the invite
    // path (build_invite_message), build_test_round_message sets no
    // Reply-To plus-tag - test-round emails aren't part of the
    // reply-matching flow the same way (see services/email_builder.py).
    const sent = await getLastSendTo(CANDIDATE_EMAIL);
    expect(sent!.html_body).toContain(TEST_URL);
    expect(sent!.subject).toContain("Assessment");
  });

  test("assessment email does not create a Draft/Approved row - status is still Sent throughout", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    await runTestRound(request, candidateId, ROUND_ASSESSMENT, TEST_URL);

    const row = await getEmailRow(candidateId);
    // Never touched Draft/Approved - test-round only ever operates on
    // an already-Sent row.
    expect(row?.status).toBe("Sent");
  });

  test("unknown candidate_id is rejected", async ({ request }) => {
    const response = await runTestRound(request, UNKNOWN_CANDIDATE_ID, ROUND_ASSESSMENT, TEST_URL);
    expect(response.status()).toBe(404);
  });

  test("unknown round_id is rejected", async ({ request, candidateId }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const response = await runTestRound(request, candidateId, UNKNOWN_ROUND_ID, TEST_URL);
    expect(response.status()).toBe(404);

    // Round did not advance.
    const row = await getEmailRow(candidateId);
    expect(row?.round_id).toBe(ROUND_INVITATION);
  });

  test("a non-assessment round_id is still accepted by test-round (no round_type gate on this endpoint)", async ({
    request,
    candidateId,
  }) => {
    // Documented in the module's own doc page: unlike /email/draft,
    // /email/test-round does not restrict by round_type - passing
    // ROUND_INVITATION here is accepted, not rejected. Testing the
    // ACTUAL behavior per the task's own instruction to verify
    // implementation over assumption.
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const response = await runTestRound(request, candidateId, ROUND_INVITATION, TEST_URL);
    expect(response.status()).toBe(200);
  });

  test("test-round against a candidate with no prior Sent email fails", async ({
    request,
    candidateId,
  }) => {
    // Candidate exists in testdata.json but has never been drafted/sent -
    // no token to resolve (see services/test_round_service.py::TokenNotFoundError).
    const response = await runTestRound(request, candidateId, ROUND_ASSESSMENT, TEST_URL);
    expect(response.status()).toBe(404);
  });

  test("missing url is rejected by request validation", async ({ request, candidateId }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const response = await request.post("/email/test-round", {
      data: { candidate_id: candidateId, round_id: ROUND_ASSESSMENT },
    });
    expect(response.status()).toBe(422); // FastAPI/Pydantic request-validation error, not the module's own 422

    const row = await getEmailRow(candidateId);
    expect(row?.round_id).toBe(ROUND_INVITATION); // unchanged
  });
});
