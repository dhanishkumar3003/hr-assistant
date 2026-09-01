import {
  test,
  expect,
  draftEmail,
  approveDraft,
  sendEmail,
  draftApproveSend,
  ROUND_INVITATION,
  HR_ID,
} from "./fixtures/email-outreach.fixture";
import { getEmailRow } from "./fixtures/db";
import { getCapturedSends, getLastSendTo } from "./fixtures/mock-postal-client";

const CANDIDATE_EMAIL = "e2e-test-candidate@example.com"; // matches provisionCandidate() in the fixture

test.describe("Sending", () => {
  test("an approved draft can be sent and transitions to Sent with tracking data", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Sent");
    expect(row?.sent_at).toBeTruthy();
    expect(row?.message_id).toBeTruthy();

    // Real 8-char tracking token assigned at send time, replacing the
    // placeholder draft token (see services/sender.py::send_approved_draft).
    expect(String(row?.token)).not.toMatch(/^draft-/);
    expect(String(row?.token)).toHaveLength(8);

    // Response deadline computed (default 72h) - see settings.response_threshold_hours.
    expect(row?.response_due_at).toBeTruthy();
    const sentAt = new Date(row?.sent_at as string).getTime();
    const dueAt = new Date(row?.response_due_at as string).getTime();
    const hoursApart = (dueAt - sentAt) / (1000 * 60 * 60);
    expect(hoursApart).toBeCloseTo(72, 0);
  });

  test("the email actually sent (via the mock Postal server) has correct recipient/subject/body", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const sent = await getLastSendTo(CANDIDATE_EMAIL);
    expect(sent, "mock Postal server never received a send for this candidate").toBeTruthy();
    expect(sent!.to).toContain(CANDIDATE_EMAIL);
    expect(sent!.subject).toContain("Interview Invitation");
    expect(sent!.subject).toMatch(/\[Ref:[a-f0-9]{8}\]/); // tracking token embedded in subject
    expect(sent!.html_body).toContain("Senior Python Developer");
    expect(sent!.reply_to).toContain(candidateId); // plus-tagged reply address, see email_builder.py
  });

  test("a Draft cannot be sent - status stays Draft", async ({ request, candidateId }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const send = await sendEmail(request, candidateId);
    expect(send.status()).toBe(409);

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Draft");
    expect(row?.sent_at).toBeNull();
  });

  test("an already-sent email cannot be sent again", async ({ request, candidateId }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const rowAfterFirstSend = await getEmailRow(candidateId);

    const secondSend = await sendEmail(request, candidateId);
    expect(secondSend.status()).toBe(409);

    const rowAfterSecondAttempt = await getEmailRow(candidateId);
    expect(rowAfterSecondAttempt?.token).toBe(rowAfterFirstSend?.token);
    expect(rowAfterSecondAttempt?.sent_at).toStrictEqual(rowAfterFirstSend?.sent_at);

    // Every candidate is unique per test (see provisionCandidate), so
    // the reply-to plus-tag lets us count sends for THIS candidate
    // specifically, proving the second /email/send attempt never
    // reached the mock Postal server at all.
    const sends = await getCapturedSends();
    const sendsForCandidate = sends.filter((s) => s.reply_to?.includes(candidateId));
    expect(sendsForCandidate).toHaveLength(1);
  });
});
