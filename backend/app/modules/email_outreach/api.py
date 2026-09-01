from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.modules.email_outreach.repositories.email_repository import EmailRepository
from app.modules.email_outreach.services.sender import EmailSenderService
from app.modules.email_outreach.services.drafter import (
    EmailDrafter,
    DraftAlreadyExistsError,
    UnsupportedRoundTypeError,
)
from app.modules.email_outreach.services.candidate_source import CandidateNotFoundError
from app.modules.email_outreach.services.approval_gate import ApprovalGate, DraftNotFoundError
from app.modules.email_outreach.services.reply_tracker import ReplyTrackerService
from app.modules.email_outreach.services.threshold_evaluator import ThresholdEvaluator
from app.modules.email_outreach.services.test_round_service import (
    TestRoundService,
    TokenNotFoundError as TestRoundTokenNotFoundError,
)
from app.modules.email_outreach.schemas import (
    TestRoundRequest,
    DraftEmailRequest,
    DraftEmailResponse,
    ApproveDraftRequest,
    RejectDraftRequest,
    SendEmailRequest,
    EmailStatusResponse,
    EmailHistoryResponse,
    ThresholdRunResponse,
    ReplyWebhookRequest,
)

router = APIRouter()


@router.get("/ping")
def ping():
    return {"module": "email_outreach", "status": "ok"}


def get_test_round_service(db: Session = Depends(get_db)) -> TestRoundService:
    """Same wiring pattern as get_response_service - the only place
    that knows TestRoundService's concrete repository."""
    return TestRoundService(email_repo=EmailRepository(db))


def get_drafter(db: Session = Depends(get_db)) -> EmailDrafter:
    return EmailDrafter(email_repo=EmailRepository(db))


def get_approval_gate(db: Session = Depends(get_db)) -> ApprovalGate:
    return ApprovalGate(email_repo=EmailRepository(db))


def get_sender_service(db: Session = Depends(get_db)) -> EmailSenderService:
    repo = EmailRepository(db)
    return EmailSenderService(email_repo=repo)


def get_email_repository(db: Session = Depends(get_db)) -> EmailRepository:
    return EmailRepository(db)


def get_reply_tracker_service(db: Session = Depends(get_db)) -> ReplyTrackerService:
    repo = EmailRepository(db)
    return ReplyTrackerService(email_repo=repo, sender=EmailSenderService(email_repo=repo))


def get_threshold_evaluator(db: Session = Depends(get_db)) -> ThresholdEvaluator:
    return ThresholdEvaluator(email_repo=EmailRepository(db))


@router.post("/test-round")
def trigger_test_round(
    request: TestRoundRequest,
    test_round_service: TestRoundService = Depends(get_test_round_service),
) -> dict:
    """
    Email a candidate their assessment link.

    Interim stand-in for the real "generate a test link" API, which
    doesn't exist yet. Whoever ends up building that service can POST
    here in the meantime with the candidate_id and the link they
    generated.

    Args:
        request (TestRoundRequest): candidate_id (public identifier),
            round_id (looked up for round name/description/duration/
            deadline/question count), and url (the assessment link).
    """
    try:
        test_round_service.send_test_round_email(
            request.candidate_id, request.round_id, request.url
        )
    except TestRoundTokenNotFoundError:
        raise HTTPException(status_code=404, detail="Unknown candidate_id")
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"status": "sent"}


@router.post("/draft", response_model=DraftEmailResponse)
def create_draft(
    request: DraftEmailRequest,
    drafter: EmailDrafter = Depends(get_drafter),
) -> DraftEmailResponse:
    """
    Generate a draft for a candidate + round (Module 3 API contract:
    POST /email/draft). Held as pending - nothing is sent until
    POST /email/approve then POST /email/send.
    """
    try:
        draft = drafter.create_draft(
            candidate_id=request.candidate_id,
            round_id=request.round_id,
        )
    except DraftAlreadyExistsError:
        raise HTTPException(
            status_code=409, detail="A pending or approved draft already exists for this candidate"
        )
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except UnsupportedRoundTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return DraftEmailResponse(**draft)


@router.post("/approve")
def approve_draft(
    request: ApproveDraftRequest,
    approval_gate: ApprovalGate = Depends(get_approval_gate),
) -> dict:
    """HR approves (optionally edits) a pending draft (Module 3 API contract: POST /email/approve)."""
    try:
        draft = approval_gate.approve(
            request.candidate_id, request.approved_by_hr_id, request.edited_body
        )
    except DraftNotFoundError:
        raise HTTPException(status_code=404, detail="No pending draft for this candidate_id")
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": draft["status"], "candidate_id": draft["candidate_id"]}


@router.post("/reject")
def reject_draft(
    request: RejectDraftRequest,
    approval_gate: ApprovalGate = Depends(get_approval_gate),
) -> dict:
    """HR rejects a pending draft - it will never be sent."""
    try:
        approval_gate.reject(request.candidate_id)
    except DraftNotFoundError:
        raise HTTPException(status_code=404, detail="No pending draft for this candidate_id")

    return {"status": "Rejected", "candidate_id": request.candidate_id}


@router.post("/send")
def send_email(
    request: SendEmailRequest,
    sender: EmailSenderService = Depends(get_sender_service),
) -> dict:
    """Send an approved draft (Module 3 API contract: POST /email/send)."""
    token = sender.send_approved_draft(request.candidate_id)
    if not token:
        raise HTTPException(
            status_code=409,
            detail="No approved draft for this candidate_id, or sending failed",
        )

    return {"status": "sent", "candidate_id": request.candidate_id}


@router.get("/status/{candidate_id}", response_model=EmailStatusResponse)
def get_status(
    candidate_id: str,
    email_repo: EmailRepository = Depends(get_email_repository),
) -> EmailStatusResponse:
    """Current outreach/reply status for a candidate (Module 3 API contract: GET /email/status/{candidate_id})."""
    status = email_repo.get_status_by_candidate_id(candidate_id)
    if not status:
        raise HTTPException(status_code=404, detail="Unknown candidate_id")

    return EmailStatusResponse(**status)


@router.get("/status/{candidate_id}/history", response_model=EmailHistoryResponse)
def get_status_history(
    candidate_id: str,
    email_repo: EmailRepository = Depends(get_email_repository),
) -> EmailHistoryResponse:
    """Full email/response history for a candidate (Module 6 status/history view)."""
    history = email_repo.get_email_history_by_candidate_id(candidate_id)
    if not history:
        raise HTTPException(status_code=404, detail="Unknown candidate_id")

    return EmailHistoryResponse(candidate_id=candidate_id, history=history)


@router.post("/threshold/run", response_model=ThresholdRunResponse)
def run_threshold_evaluation(
    threshold_evaluator: ThresholdEvaluator = Depends(get_threshold_evaluator),
) -> ThresholdRunResponse:
    """
    Run the response-threshold job on demand: marks every Sent
    candidate past settings.response_threshold_hours with no reply on
    record as Inactive. A scheduler/cron can hit this endpoint directly
    instead of running it manually.
    """
    marked = threshold_evaluator.mark_overdue_inactive()
    return ThresholdRunResponse(marked_inactive=marked)


@router.post("/webhook/reply")
def webhook_reply(
    request: ReplyWebhookRequest,
    reply_tracker: ReplyTrackerService = Depends(get_reply_tracker_service),
) -> dict:
    """
    Inbound webhook when a reply is detected (Module 3 API contract:
    POST /email/webhook/reply).

    Thin wrapper over ReplyTrackerService.process_reply() - the same
    record/classify/confirm sequence the poll/Pub-Sub loop
    (services/reply_tracker.py::monitor_replies) already uses, so both
    delivery mechanisms converge on one code path. Wire a real mail
    provider's webhook to POST here with the parsed token/subject/body
    to switch from polling to push without touching this logic.
    """
    classification = reply_tracker.process_reply(
        request.token,
        request.subject,
        request.body,
        request.received_at or datetime.now(timezone.utc),
    )

    return {"status": "processed", "classification": classification}
