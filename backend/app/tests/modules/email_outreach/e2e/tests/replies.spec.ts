import {
  test,
  expect,
  draftApproveSend,
  sendWebhookReply,
  getStatus,
  ROUND_INVITATION,
} from "./fixtures/email-outreach.fixture";
import { getTokenForCandidate } from "./fixtures/db";
import { getLastSendTo } from "./fixtures/mock-postal-client";

async function sendAndGetToken(request: any, candidateId: string): Promise<string> {
  await draftApproveSend(request, candidateId, ROUND_INVITATION);
  const token = await getTokenForCandidate(candidateId);
  expect(token, "no tracking token found after send").toBeTruthy();
  return token as string;
}

test.describe("Candidate reply classification", () => {
  for (const body of [
    "Yes, I am interested.",
    "Sounds good, please proceed.",
    "I would like to continue with the interview.",
  ]) {
    test(`classifies as interested: "${body}"`, async ({ request, candidateId }) => {
      const token = await sendAndGetToken(request, candidateId);

      const reply = await sendWebhookReply(request, token, body);
      expect(reply.status()).toBe(200);
      const replyBody = await reply.json();
      expect(replyBody.classification).toBe("interested");

      const status = await getStatus(request, candidateId);
      const statusBody = await status.json();
      expect(statusBody.has_responded).toBe(true);
      expect(statusBody.classification).toBe("interested");
    });
  }

  for (const body of [
    "Thanks, but I am not interested.",
    "I would like to decline the opportunity.",
    "I don't want to proceed.",
  ]) {
    test(`classifies as declined: "${body}"`, async ({ request, candidateId }) => {
      const token = await sendAndGetToken(request, candidateId);

      const reply = await sendWebhookReply(request, token, body);
      expect(reply.status()).toBe(200);
      const replyBody = await reply.json();
      expect(replyBody.classification).toBe("declined");

      const status = await getStatus(request, candidateId);
      const statusBody = await status.json();
      expect(statusBody.classification).toBe("declined");
    });
  }

  for (const body of [
    "Can you send me more information about the role?",
    "I have a question regarding the position.",
  ]) {
    test(`ambiguous reply goes to needs_review, not a false positive: "${body}"`, async ({
      request,
      candidateId,
    }) => {
      const token = await sendAndGetToken(request, candidateId);

      const reply = await sendWebhookReply(request, token, body);
      expect(reply.status()).toBe(200);
      const replyBody = await reply.json();
      // The application's actual states are interested/declined/
      // needs_review (there is no literal "OTHER" surfaced by the
      // API - that's the LLM's own internal label before mapping,
      // see services/reply_classifier.py's _LLM_LABEL_TO_CLASSIFICATION).
      expect(replyBody.classification).toBe("needs_review");
    });
  }

  test("typo/casual phrasing is still read as interested, not dismissed to needs_review", async ({
    request,
    candidateId,
  }) => {
    const token = await sendAndGetToken(request, candidateId);

    const reply = await sendWebhookReply(request, token, "Intrested, yes pls.");
    expect(reply.status()).toBe(200);
    const replyBody = await reply.json();
    expect(replyBody.classification).toBe("interested");
  });

  test("an automated confirmation email is sent after classification", async ({
    request,
    candidateId,
  }) => {
    const token = await sendAndGetToken(request, candidateId);
    await sendWebhookReply(request, token, "Yes, I am very interested!");

    const sent = await getLastSendTo("e2e-test-candidate@example.com");
    // Two sends now exist for this candidate: the original invite,
    // then the confirmation - getLastSendTo returns the most recent,
    // whose subject/body come from confirmation_content.py's
    // CLASSIFICATION_INTERESTED entry, not the invite template.
    expect(sent!.subject).toBe("Thanks for Your Response");
  });
});
