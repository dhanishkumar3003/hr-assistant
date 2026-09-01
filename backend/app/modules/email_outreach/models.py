"""
ORM models for the email_outreach module - emails / candidate_responses.

Ported from a standalone email-automation project. Fields beyond a
typical outreach schema (token, candidate_id, message_id) exist because
that project matches candidate replies via a subject-embedded token,
a public candidate_id (Reply-To plus-tag, draft/status APIs), and
Message-ID threading - not Module 1 candidate records, which this
module doesn't depend on yet.
"""

from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, Numeric, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Email(Base):
    __tablename__ = "email_outreach_emails"

    email_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Public-facing identifier - a UUID generated per candidate/send,
    # used in the Reply-To plus-tag and the draft/status/test-round
    # APIs instead of exposing the internal token. token (below) stays
    # purely for matching replies via the subject line - it's
    # unrelated to this.
    candidate_id: Mapped[str | None] = mapped_column(String(36), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    # Which round this email represents (see services/candidate_source.py
    # ::fetch_round and app/tests/modules/email_outreach/testdata.json's rounds[]
    # catalog) - round_number lets GET /email/status report "candidate
    # is on round N" directly; round_id is the specific catalog entry
    # sent (e.g. ROUND-2-BACKEND vs ROUND-2-FRONTEND both being round 2).
    round_id: Mapped[str | None] = mapped_column(String(64))
    round_number: Mapped[int | None] = mapped_column(Integer)
    # Message-ID header of the sent invite - the primary reply-matching
    # signal (see services/reply_matcher.py). A reply's In-Reply-To/
    # References points back to this, which survives subject edits and
    # doesn't depend on any text the candidate types.
    message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    candidate_email: Mapped[str] = mapped_column(String(255))
    candidate_name: Mapped[str | None] = mapped_column(String(255))
    # Snapshotted at send time so the response/confirmation flow (see
    # services/sender.py::send_confirmation) can render a correct
    # confirmation email later without depending on candidate_source's
    # current state.
    job_role: Mapped[str | None] = mapped_column(String(255))
    company_name: Mapped[str | None] = mapped_column(String(255))
    hr_name: Mapped[str | None] = mapped_column(String(255))
    hr_designation: Mapped[str | None] = mapped_column(String(255))
    hr_email: Mapped[str | None] = mapped_column(String(255))
    recipient_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    email_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    resend_count: Mapped[int] = mapped_column(Integer, default=0)
    last_resent_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_resend_at: Mapped[datetime | None] = mapped_column(DateTime)
    resend_reason: Mapped[str | None] = mapped_column(String(100))
    is_resend: Mapped[bool] = mapped_column(Boolean, default=False)


class CandidateResponse(Base):
    __tablename__ = "email_outreach_candidate_responses"

    response_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_outreach_emails.email_id"))
    subject: Mapped[str] = mapped_column(String(500))
    response_body: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(100))
    intent_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # How this response was captured/classified: "reply_email_regex"
    # (matched a rule in services/reply_classifier.py), or
    # "reply_email_llm" (fell through to the Ollama classifier). See
    # reply_classifier.SOURCE_*.
    classification_source: Mapped[str | None] = mapped_column(String(30))
    received_at: Mapped[datetime] = mapped_column(DateTime)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    candidate_requested_date: Mapped[datetime | None] = mapped_column(DateTime)
    trigger_date: Mapped[datetime | None] = mapped_column(DateTime)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False)
