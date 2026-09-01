import {
  test,
  expect,
  draftEmail,
  rejectDraft,
  sendEmail,
  getHistory,
  ROUND_INVITATION,
} from "./fixtures/email-outreach.fixture";
import { getEmailRow } from "./fixtures/db";

test.describe("HR rejection", () => {
  test("rejecting a draft moves it to Rejected", async ({ request, candidateId }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const reject = await rejectDraft(request, candidateId);
    expect(reject.status()).toBe(200);
    const body = await reject.json();
    expect(body.status).toBe("Rejected");

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Rejected");
  });

  test("a rejected draft cannot subsequently be sent", async ({ request, candidateId }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);
    await rejectDraft(request, candidateId);

    const send = await sendEmail(request, candidateId);
    expect(send.status()).toBe(409);

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Rejected");
    expect(row?.sent_at).toBeNull();
  });

  test("rejected record remains visible in history and no email was delivered", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);
    await rejectDraft(request, candidateId);

    const history = await getHistory(request, candidateId);
    expect(history.status()).toBe(200);
    const body = await history.json();
    expect(body.history.some((e: any) => e.event === "email_rejected")).toBeTruthy();

    const row = await getEmailRow(candidateId);
    expect(row?.sent_at).toBeNull();
    expect(row?.message_id).toBeNull();
  });

  test("rejecting a non-existent draft fails", async ({ request, candidateId }) => {
    const reject = await rejectDraft(request, candidateId);
    expect(reject.status()).toBe(404);
  });

  test("rejecting twice - second attempt fails, status stays Rejected", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);
    const first = await rejectDraft(request, candidateId);
    expect(first.status()).toBe(200);

    const second = await rejectDraft(request, candidateId);
    expect(second.status()).toBe(404);

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Rejected");
  });
});
