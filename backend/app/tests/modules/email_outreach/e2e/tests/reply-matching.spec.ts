import {
  test,
  expect,
  draftApproveSend,
  sendWebhookReply,
  getStatus,
  ROUND_INVITATION,
} from "./fixtures/email-outreach.fixture";
import { getTokenForCandidate } from "./fixtures/db";

/**
 * Reply-matching signal coverage.
 *
 * IMPORTANT LIMITATION (see README.md "Remaining limitations" for the
 * full writeup): services/reply_matcher.py's three-signal matching
 * (Message-ID threading, plus-tag, subject token) only runs inside
 * GmailPubSubBackend._resolve_new_messages, which requires a live
 * Gmail push notification carrying real raw email bytes. There is no
 * HTTP endpoint that accepts raw email bytes for matching - POST
 * /email/webhook/reply takes an ALREADY-RESOLVED token directly and
 * never touches reply_matcher.py at all. That module's three signals
 * are therefore not exercisable through the application's API surface
 * without a real Gmail mailbox, and are NOT tested here - doing so
 * would mean importing the Python parser directly, which tests the
 * parser in isolation rather than the running application.
 *
 * What IS testable through the webhook: the "known token" vs "unknown
 * token" behavior at the process_reply() boundary itself, and the
 * quoted-text stripping that already runs regardless of how a reply
 * arrived (see services/reply_tracker.py::process_reply, which calls
 * strip_quoted_content before both storage and classification).
 */
test.describe("Reply matching (webhook boundary)", () => {
  test("a reply for a known token is associated with the correct candidate", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const token = await getTokenForCandidate(candidateId);

    const reply = await sendWebhookReply(request, token as string, "Yes, interested!");
    expect(reply.status()).toBe(200);

    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.candidate_id).toBe(candidateId);
    expect(statusBody.has_responded).toBe(true);
  });

  test("a reply for an unknown/unmatched token is handled safely, no candidate is modified", async ({
    request,
    candidateId,
  }) => {
    // A different, real candidate exists alongside this one - prove
    // an unknown-token reply doesn't touch it.
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const statusBefore = await (await getStatus(request, candidateId)).json();

    const reply = await sendWebhookReply(
      request,
      "totally-unknown-token-000",
      "This reply matches nothing."
    );
    // process_reply() records/classifies against whatever token it's
    // given - record_reply on an unknown token is a documented no-op
    // (see repositories/email_repository.py: "unknown token" cases),
    // so this returns 200 with a needs_review-shaped result rather
    // than a 404, and crucially does not touch any real candidate.
    expect(reply.status()).toBe(200);

    const statusAfter = await (await getStatus(request, candidateId)).json();
    expect(statusAfter.has_responded).toBe(statusBefore.has_responded);
    expect(statusAfter.classification).toBe(statusBefore.classification);
  });

  test("quoted/forwarded original content does not flip classification (Decline button text in the quote)", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);
    const token = await getTokenForCandidate(candidateId);

    // The quoted block below contains "decline" (a REPLY_DECLINED_PATTERNS
    // match) purely because it's our own invite's boilerplate - the
    // real reply text says nothing of the sort.
    const body = [
      "Yes, I am interested.",
      "",
      "--- Original Message ---",
      "You can decline this interview invitation by replying \"not interested\".",
    ].join("\n");

    const reply = await sendWebhookReply(request, token as string, body);
    expect(reply.status()).toBe(200);
    const replyBody = await reply.json();
    expect(replyBody.classification).toBe("interested");
  });
});
