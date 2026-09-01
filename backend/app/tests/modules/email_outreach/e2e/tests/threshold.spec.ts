import {
  test,
  expect,
  draftApproveSend,
  sendWebhookReply,
  rejectDraft,
  draftEmail,
  runThreshold,
  getStatus,
  ROUND_INVITATION,
} from "./fixtures/email-outreach.fixture";
import { backdateResponseDeadline, getTokenForCandidate } from "./fixtures/db";

test.describe("Threshold / auto-inactive", () => {
  test("a Sent candidate past their response deadline with no reply becomes Inactive", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    await backdateResponseDeadline(candidateId, 1); // 1 hour past due

    const response = await runThreshold(request);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.marked_inactive).toContain(candidateId);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Inactive");
  });

  test("a candidate whose deadline has NOT passed is left unchanged", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    // Push the deadline INTO the future (negative hours-ago) - still well within window.
    await backdateResponseDeadline(candidateId, -48);

    const response = await runThreshold(request);
    const body = await response.json();
    expect(body.marked_inactive).not.toContain(candidateId);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Sent");
  });

  test("a candidate who already replied is not marked inactive even past deadline", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const token = await getTokenForCandidate(candidateId);
    await sendWebhookReply(request, token as string, "Yes, interested!");
    await backdateResponseDeadline(candidateId, 1);

    const response = await runThreshold(request);
    const body = await response.json();
    expect(body.marked_inactive).not.toContain(candidateId);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Sent"); // reply doesn't change email_status, only has_responded
  });

  test("an already-rejected record is not changed by the threshold job", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);
    await rejectDraft(request, candidateId);

    const response = await runThreshold(request);
    const body = await response.json();
    expect(body.marked_inactive).not.toContain(candidateId);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Rejected");
  });
});
