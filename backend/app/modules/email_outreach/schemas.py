"""
Request/response data contracts for the email_outreach API.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class TestRoundRequest(BaseModel):
    """
    Body for POST /email/test-round.

    candidate_id is the same public identifier embedded in outreach
    emails (see services/tracking_token_service.py) - a UUID generated
    per candidate at send time, stored in Email.candidate_id and
    resolved internally to the tracking token.

    round_id alone is enough to fill in the round's name, description,
    duration, deadline, and question count - resolved server-side via
    the configured candidate source (testdata.json today - see
    services/candidate_source.py::fetch_round).
    """

    candidate_id: str = Field(..., description="Public candidate identifier (UUID)")
    round_id: str = Field(..., description="Test round identifier - looked up for round details")
    url: str = Field(..., description="The assessment/test link to send")


class DraftEmailRequest(BaseModel):
    """
    Body for POST /email/draft - Module 2 (chatbot) asks for a draft
    for one candidate + round.

    candidate_id + round_id alone are enough: the candidate's email/
    name, the job/HR details their record points to (job_id/hr_id),
    and the round's name/type/number are all resolved server-side via
    the configured candidate source (testdata.json today - see
    services/candidate_source.py). round_id must resolve to a round
    whose round_type is invitation/next_round/rejection - "assessment"
    rounds go through POST /email/test-round instead, not this endpoint.
    """

    candidate_id: str = Field(..., description="Public candidate identifier (Module 1/2-issued)")
    round_id: str = Field(
        "ROUND-1",
        description="Round identifier from the rounds[] catalog - selects the "
        "template/subject via the round's round_type, and its round_number is "
        "stored for progress tracking",
    )


class DraftEmailResponse(BaseModel):
    candidate_id: str
    subject: str
    body: str
    email_type: str
    status: str
    round_id: str | None = None
    round_number: int | None = None


class ApproveDraftRequest(BaseModel):
    """Body for POST /email/approve."""

    candidate_id: str = Field(..., description="Public candidate identifier")
    approved_by_hr_id: str | None = Field(
        None,
        description="hr_id of the HR user approving the draft - looked up via the "
        "configured candidate source (testdata.json today) and stored as their name",
    )
    edited_body: str | None = Field(None, description="Replacement HTML body, if HR edited it")


class RejectDraftRequest(BaseModel):
    candidate_id: str = Field(..., description="Public candidate identifier")


class SendEmailRequest(BaseModel):
    """Body for POST /email/send - sends a draft already approved via /email/approve."""

    candidate_id: str = Field(..., description="Public candidate identifier")


class EmailStatusResponse(BaseModel):
    candidate_id: str
    email_status: str
    round_id: str | None = None
    round_number: int | None = None
    sent_at: datetime | None = None
    response_due_at: datetime | None = None
    has_responded: bool
    classification: str | None = None
    received_at: datetime | None = None


class EmailHistoryEvent(BaseModel):
    event: str
    at: datetime | None = None
    subject: str | None = None
    email_type: str | None = None
    round_id: str | None = None
    round_number: int | None = None
    classification: str | None = None
    classification_source: str | None = None


class EmailHistoryResponse(BaseModel):
    candidate_id: str
    history: list[EmailHistoryEvent]


class ThresholdRunResponse(BaseModel):
    marked_inactive: list[str]


class ReplyWebhookRequest(BaseModel):
    """
    Body for POST /email/webhook/reply.

    Interim payload shape for a generic inbound-reply webhook. The
    module's primary reply-detection path today is
    services/reply_tracker.py's poll/Pub-Sub loop (see PORT_NOTES.md);
    this endpoint exists so a real mail-provider webhook can be wired
    in later without changing anything downstream - it calls the exact
    same ReplyTrackerService.process_reply() the poll loop uses.
    """

    token: str = Field(..., description="Tracking token parsed from the reply subject/thread")
    subject: str = Field("", description="Reply subject line")
    body: str = Field(..., description="Reply body text")
    received_at: datetime | None = Field(None, description="When the reply was received")
