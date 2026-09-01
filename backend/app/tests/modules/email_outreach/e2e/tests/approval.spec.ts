import {
  test,
  expect,
  draftEmail,
  approveDraft,
  rejectDraft,
  sendEmail,
  getStatus,
  draftApproveSend,
  ROUND_INVITATION,
  HR_ID,
  UNKNOWN_HR_ID,
} from "./fixtures/email-outreach.fixture";
import { getEmailRow } from "./fixtures/db";

test.describe("HR approval", () => {
  test("approving a draft moves it to Approved and records the approver", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const approve = await approveDraft(request, candidateId, { approvedByHrId: HR_ID });
    expect(approve.status()).toBe(200);
    const approveBody = await approve.json();
    expect(approveBody.status).toBe("Approved");
    expect(approveBody.candidate_id).toBe(candidateId);

    // approved_by_hr_id resolves to the HR record's NAME in the DB
    // (see services/approval_gate.py) - not the raw id.
    const row = await getEmailRow(candidateId);
    expect(row?.approved_by).toBe("Priya Sharma");
    expect(row?.approved_at).toBeTruthy();
    expect(row?.status).toBe("Approved");

    // Still unsent.
    expect(row?.sent_at).toBeNull();
    const status = await getStatus(request, candidateId);
    const statusBody = await status.json();
    expect(statusBody.email_status).toBe("Approved");
    expect(statusBody.sent_at).toBeNull();
  });

  test("HR-edited body is preserved through to send, not regenerated", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const editedBody = "<p>This is a hand-edited body the tests will look for verbatim.</p>";
    const approve = await approveDraft(request, candidateId, {
      approvedByHrId: HR_ID,
      editedBody,
    });
    expect(approve.status()).toBe(200);

    const rowAfterApprove = await getEmailRow(candidateId);
    expect(rowAfterApprove?.body).toBe(editedBody);

    const send = await sendEmail(request, candidateId);
    expect(send.status()).toBe(200);

    // send_approved_draft sends the stored body as-is, no re-render -
    // see services/sender.py::send_approved_draft.
    const rowAfterSend = await getEmailRow(candidateId);
    expect(rowAfterSend?.body).toBe(editedBody);
  });

  test("approving a candidate with no pending draft fails", async ({ request, candidateId }) => {
    const response = await approveDraft(request, candidateId, { approvedByHrId: HR_ID });
    expect(response.status()).toBe(404);
  });

  test("approving an already-sent email is rejected and leaves it Sent", async ({
    request,
    candidateId,
  }) => {
    await draftApproveSend(request, candidateId, ROUND_INVITATION);

    const rowBefore = await getEmailRow(candidateId);
    expect(rowBefore?.status).toBe("Sent");

    const secondApprove = await approveDraft(request, candidateId, { approvedByHrId: HR_ID });
    expect(secondApprove.status()).toBe(404);

    const rowAfter = await getEmailRow(candidateId);
    expect(rowAfter?.status).toBe("Sent");
    expect(rowAfter?.sent_at).toStrictEqual(rowBefore?.sent_at);
  });

  test("unknown approving HR id is rejected", async ({ request, candidateId }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const approve = await approveDraft(request, candidateId, { approvedByHrId: UNKNOWN_HR_ID });
    expect(approve.status()).toBe(404);

    // Draft stays Draft - the failed hr_id lookup happens before any
    // state mutation (see services/approval_gate.py::approve).
    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Draft");
    expect(row?.approved_by).toBeNull();
  });

  test("approving without a hr id is allowed (optional field)", async ({
    request,
    candidateId,
  }) => {
    await draftEmail(request, candidateId, ROUND_INVITATION);

    const approve = await approveDraft(request, candidateId, {});
    expect(approve.status()).toBe(200);

    const row = await getEmailRow(candidateId);
    expect(row?.status).toBe("Approved");
    expect(row?.approved_by).toBeNull();
  });
});
