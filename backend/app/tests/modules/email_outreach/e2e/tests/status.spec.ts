import {
  test,
  expect,
  draftEmail,
  draftApproveSend,
  sendWebhookReply,
  getStatus,
  getHistory,
  ROUND_INVITATION,
  ROUND_ASSESSMENT,
  UNKNOWN_CANDIDATE_ID,
} from "./fixtures/email-outreach.fixture";
import { getTokenForCandidate } from "./fixtures/db";

test.describe("Status", () => {
  test("status reflects current email/round state for a Draft candidate", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const response = await getStatus(request, candidateId);
    expect(response.status()).toBe(200);
    const body = await response.json();

    expect(body.candidate_id).toBe(candidateId);
    expect(body.email_status).toBe("Draft");
    expect(body.round_id).toBe(ROUND_INVITATION);
    expect(body.round_number).toBeNull();
    expect(body.has_responded).toBe(false);
    expect(body.classification).toBeNull();
    expect(body.sent_at).toBeNull();
  });

  test("status reflects Sent state with timestamps and reply classification", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const token = await getTokenForCandidate(candidateId);
    await sendWebhookReply(request, token as string, "Yes, interested!");

    const response = await getStatus(request, candidateId);
    const body = await response.json();

    expect(body.email_status).toBe("Sent");
    expect(body.sent_at).toBeTruthy();
    expect(body.response_due_at).toBeTruthy();
    expect(body.has_responded).toBe(true);
    expect(body.classification).toBe("interested");
    expect(body.received_at).toBeTruthy();
  });

  test("status for unknown candidate is 404", async ({ request }) => {
    const response = await getStatus(request, UNKNOWN_CANDIDATE_ID);
    expect(response.status()).toBe(404);
  });

  test("history is chronologically ordered and contains draft/approve/send/reply events", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const token = await getTokenForCandidate(candidateId);
    await sendWebhookReply(request, token as string, "Yes, interested!");

    const response = await getHistory(request, candidateId);
    expect(response.status()).toBe(200);
    const body = await response.json();

    expect(body.candidate_id).toBe(candidateId);
    expect(Array.isArray(body.history)).toBe(true);

    const events = body.history.map((e: any) => e.event);
    // email_approved is the final Email-row event by the time history
    // is read (draft->approved->sent all mutate the SAME row, so only
    // its latest status shows as one "email_*" event - see
    // repositories/email_repository.py::get_email_history_by_candidate_id),
    // followed by the reply.
    expect(events).toContain("email_sent");
    expect(events).toContain("reply_received");

    // Chronological order - every event's timestamp is >= the previous one.
    const timestamps = body.history
      .map((e: any) => (e.at ? new Date(e.at).getTime() : null))
      .filter((t: number | null): t is number => t !== null);
    for (let i = 1; i < timestamps.length; i++) {
      expect(timestamps[i]).toBeGreaterThanOrEqual(timestamps[i - 1]);
    }

    const replyEvent = body.history.find((e: any) => e.event === "reply_received");
    expect(replyEvent.classification).toBe("interested");
  });

  test("history after reject+redraft shows both attempts", async ({ request, candidateId }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);
    await request.post("/email/reject", { data: { candidate_id: candidateId } });
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const response = await getHistory(request, candidateId);
    const body = await response.json();
    const events = body.history.map((e: any) => e.event);

    expect(events).toContain("email_rejected");
    expect(events).toContain("email_draft");
  });
});
