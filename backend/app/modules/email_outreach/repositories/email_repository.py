"""
DB access for the email_outreach module - only class allowed to query
or write email_outreach_emails / email_outreach_candidate_responses
directly.

Ported from a standalone project's state_manager.py (flat functions
over a module-level SessionLocal) into this repository pattern (a
request-scoped Session injected via app.core.deps.get_db) - the
queries and behavior are unchanged, only how the session gets here.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.email_outreach.models import Email, CandidateResponse

EMAIL_TYPE_INTERVIEW_INVITATION = "interview_invitation"
EMAIL_TYPE_NEXT_ROUND_INVITATION = "next_round_invitation"
EMAIL_TYPE_CANDIDATE_REJECTION = "candidate_rejection"
STATUS_DRAFT = "Draft"
STATUS_APPROVED = "Approved"
STATUS_SENT = "Sent"
STATUS_REJECTED = "Rejected"
STATUS_INACTIVE = "Inactive"


class IEmailRepository(ABC):
    @abstractmethod
    def save_sent_email(
        self,
        token: str,
        candidate_email: str,
        candidate_name: str,
        subject: str,
        body: str,
        sent_at: datetime,
        template_context: dict = None,
        candidate_id: str = None,
        message_id: str = None,
    ) -> None: ...

    @abstractmethod
    def get_pending_tokens(self) -> list[str]: ...

    @abstractmethod
    def get_candidate_email(self, token: str) -> str | None: ...

    @abstractmethod
    def get_token_by_candidate_id(self, candidate_id: str) -> str | None: ...

    @abstractmethod
    def get_token_by_message_id(self, message_id: str) -> str | None: ...

    @abstractmethod
    def get_email_record(self, token: str) -> dict | None: ...

    @abstractmethod
    def has_responded(self, token: str) -> bool: ...

    @abstractmethod
    def record_reply(self, token: str, subject: str, body: str, received_at: datetime) -> None: ...

    @abstractmethod
    def get_reply_body(self, token: str) -> str | None: ...

    @abstractmethod
    def set_classification(
        self, token: str, classification: str, analyzed_at: datetime, source: str = None
    ) -> None: ...

    @abstractmethod
    def save_draft(
        self,
        candidate_id: str,
        candidate_email: str,
        candidate_name: str,
        subject: str,
        body: str,
        email_type: str,
        template_context: dict = None,
        round_id: str = None,
        round_number: int = None,
    ) -> None: ...

    @abstractmethod
    def get_draft_by_candidate_id(self, candidate_id: str) -> dict | None: ...

    @abstractmethod
    def approve_draft(
        self, candidate_id: str, approved_by: str = None, edited_body: str = None
    ) -> None: ...

    @abstractmethod
    def reject_draft(self, candidate_id: str) -> None: ...

    @abstractmethod
    def mark_sent(
        self,
        candidate_id: str,
        token: str,
        sent_at: datetime,
        message_id: str = None,
        response_due_at: datetime = None,
    ) -> None: ...

    @abstractmethod
    def update_round(self, candidate_id: str, round_id: str, round_number: int = None) -> None: ...

    @abstractmethod
    def get_status_by_candidate_id(self, candidate_id: str) -> dict | None: ...

    @abstractmethod
    def get_overdue_sent_candidate_ids(self, as_of: datetime) -> list[str]: ...

    @abstractmethod
    def get_email_history_by_candidate_id(self, candidate_id: str) -> list[dict]: ...

    @abstractmethod
    def mark_inactive(self, candidate_id: str) -> None: ...


class EmailRepository(IEmailRepository):
    """SQLAlchemy-backed IEmailRepository. Takes a request-scoped Session."""

    def __init__(self, db: Session):
        self._db = db

    def save_sent_email(
        self,
        token: str,
        candidate_email: str,
        candidate_name: str,
        subject: str,
        body: str,
        sent_at: datetime,
        template_context: dict = None,
        candidate_id: str = None,
        message_id: str = None,
    ) -> None:
        """
        Record a newly sent invitation email.

        Snapshots job_role/company_name/hr_* from template_context so
        the response/confirmation flow can render a correct
        confirmation email later without depending on
        candidate_source's current state.
        """
        context = template_context or {}

        self._db.add(
            Email(
                token=token,
                candidate_id=candidate_id,
                message_id=message_id,
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                job_role=context.get("job_role"),
                company_name=context.get("company_name"),
                hr_name=context.get("hr_name"),
                hr_designation=context.get("hr_designation"),
                hr_email=context.get("hr_email"),
                recipient_email=candidate_email,
                subject=subject,
                body=body,
                email_type=EMAIL_TYPE_INTERVIEW_INVITATION,
                status=STATUS_SENT,
                sent_at=sent_at,
            )
        )
        self._db.commit()

    def get_pending_tokens(self) -> list[str]:
        """Tokens for sent emails that have no reply yet."""
        rows = (
            self._db.query(Email.token)
            .outerjoin(CandidateResponse, CandidateResponse.email_id == Email.email_id)
            .filter(CandidateResponse.response_id.is_(None))
            .all()
        )
        return [row.token for row in rows]

    def get_candidate_email(self, token: str) -> str | None:
        """Expected candidate email address for a token."""
        email = self._db.query(Email).filter(Email.token == token).first()
        return email.candidate_email if email else None

    def get_token_by_candidate_id(self, candidate_id: str) -> str | None:
        """
        Resolve the public-facing candidate_id to its internal token.

        Used only at the API boundary - everything past that point
        (record_reply, set_classification, get_email_record, etc.)
        keeps working with token exactly as before, so switching the
        public identifier didn't require touching the reply-matching
        path.
        """
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id)
            .order_by(Email.created_at.desc())
            .first()
        )
        return email.token if email else None

    def get_token_by_message_id(self, message_id: str) -> str | None:
        """Resolve a referenced Message-ID to its internal token (see reply_matcher.py)."""
        email = self._db.query(Email).filter(Email.message_id == message_id).first()
        return email.token if email else None

    def get_email_record(self, token: str) -> dict | None:
        """
        Stored email record for a token.

        Used to render a confirmation email without depending on
        candidate_source's current state.
        """
        email = self._db.query(Email).filter(Email.token == token).first()
        if not email:
            return None

        return {
            "candidate_email": email.candidate_email,
            "candidate_name": email.candidate_name,
            "job_role": email.job_role,
            "company_name": email.company_name,
            "hr_name": email.hr_name,
            "hr_designation": email.hr_designation,
            "hr_email": email.hr_email,
        }

    def has_responded(self, token: str) -> bool:
        """Whether a candidate has already responded to this token (rejects duplicate link clicks)."""
        email = self._db.query(Email).filter(Email.token == token).first()
        if not email:
            return False

        exists = (
            self._db.query(CandidateResponse)
            .filter(CandidateResponse.email_id == email.email_id)
            .first()
        )
        return exists is not None

    def record_reply(self, token: str, subject: str, body: str, received_at: datetime) -> None:
        """Record a candidate's reply against its tracking token."""
        email = self._db.query(Email).filter(Email.token == token).first()
        if not email:
            return

        self._db.add(
            CandidateResponse(
                email_id=email.email_id,
                subject=subject,
                response_body=body,
                received_at=received_at,
            )
        )
        self._db.commit()

    def get_reply_body(self, token: str) -> str | None:
        """Most recent unclassified reply body for a token."""
        response = (
            self._db.query(CandidateResponse)
            .join(Email, Email.email_id == CandidateResponse.email_id)
            .filter(Email.token == token, CandidateResponse.intent.is_(None))
            .order_by(CandidateResponse.received_at.desc())
            .first()
        )
        return response.response_body if response else None

    def set_classification(
        self, token: str, classification: str, analyzed_at: datetime, source: str = None
    ) -> None:
        """Store the classification result for a candidate's reply."""
        response = (
            self._db.query(CandidateResponse)
            .join(Email, Email.email_id == CandidateResponse.email_id)
            .filter(Email.token == token, CandidateResponse.intent.is_(None))
            .order_by(CandidateResponse.received_at.desc())
            .first()
        )
        if not response:
            return

        response.intent = classification
        response.analyzed_at = analyzed_at
        response.classification_source = source
        self._db.commit()

    def save_draft(
        self,
        candidate_id: str,
        candidate_email: str,
        candidate_name: str,
        subject: str,
        body: str,
        email_type: str,
        template_context: dict = None,
        round_id: str = None,
        round_number: int = None,
    ) -> None:
        """
        Record an HR-pending email draft. No token yet - the tracking
        token is only generated at send time (approve_draft/mark_sent),
        since it's embedded in the subject line that actually goes out.
        A placeholder unique token is used here to satisfy the
        not-null/unique column until send time - suffixed with a short
        uuid fragment so a candidate can be re-drafted (e.g. after a
        rejected attempt) without colliding with their prior draft's
        placeholder token.
        """
        context = template_context or {}

        self._db.add(
            Email(
                token=f"draft-{candidate_id}-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate_id,
                round_id=round_id,
                round_number=round_number,
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                job_role=context.get("job_role"),
                company_name=context.get("company_name"),
                hr_name=context.get("hr_name"),
                hr_designation=context.get("hr_designation"),
                hr_email=context.get("hr_email"),
                recipient_email=candidate_email,
                subject=subject,
                body=body,
                email_type=email_type,
                status=STATUS_DRAFT,
            )
        )
        self._db.commit()

    def get_draft_by_candidate_id(self, candidate_id: str) -> dict | None:
        """Pending/approved draft for a candidate, if one exists."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id, Email.status.in_((STATUS_DRAFT, STATUS_APPROVED)))
            .first()
        )
        if not email:
            return None

        return {
            "candidate_id": email.candidate_id,
            "candidate_email": email.candidate_email,
            "candidate_name": email.candidate_name,
            "subject": email.subject,
            "body": email.body,
            "email_type": email.email_type,
            "status": email.status,
            "round_id": email.round_id,
            "round_number": email.round_number,
            "job_role": email.job_role,
            "company_name": email.company_name,
            "hr_name": email.hr_name,
            "hr_designation": email.hr_designation,
            "hr_email": email.hr_email,
        }

    def approve_draft(
        self, candidate_id: str, approved_by: str = None, edited_body: str = None
    ) -> None:
        """Move a pending draft to Approved, optionally applying HR edits to the body."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id, Email.status == STATUS_DRAFT)
            .first()
        )
        if not email:
            return

        if edited_body is not None:
            email.body = edited_body
        email.status = STATUS_APPROVED
        email.approved_at = datetime.utcnow()
        email.approved_by = approved_by
        self._db.commit()

    def reject_draft(self, candidate_id: str) -> None:
        """Mark a pending draft as rejected - it will never be sent."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id, Email.status == STATUS_DRAFT)
            .first()
        )
        if not email:
            return

        email.status = STATUS_REJECTED
        self._db.commit()

    def mark_sent(
        self,
        candidate_id: str,
        token: str,
        sent_at: datetime,
        message_id: str = None,
        response_due_at: datetime = None,
    ) -> None:
        """Assign the real tracking token and flip an approved draft to Sent."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id, Email.status == STATUS_APPROVED)
            .first()
        )
        if not email:
            return

        email.token = token
        email.message_id = message_id
        email.status = STATUS_SENT
        email.sent_at = sent_at
        email.response_due_at = response_due_at
        self._db.commit()

    def update_round(self, candidate_id: str, round_id: str, round_number: int = None) -> None:
        """
        Record which round a test-round assessment email advanced the
        candidate to. Updates the candidate's current (most recent)
        Email row rather than inserting a new one - POST
        /email/test-round sends against an existing Sent row (see
        services/test_round_service.py) instead of drafting a new
        email, so round progress is tracked on that same row.
        """
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id)
            .order_by(Email.created_at.desc())
            .first()
        )
        if not email:
            return

        email.round_id = round_id
        email.round_number = round_number
        self._db.commit()

    def get_status_by_candidate_id(self, candidate_id: str) -> dict | None:
        """Current outreach/reply status for a candidate (GET /email/status/{candidate_id})."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id)
            .order_by(Email.created_at.desc())
            .first()
        )
        if not email:
            return None

        response = (
            self._db.query(CandidateResponse)
            .filter(CandidateResponse.email_id == email.email_id)
            .order_by(CandidateResponse.received_at.desc())
            .first()
        )

        return {
            "candidate_id": email.candidate_id,
            "email_status": email.status,
            "round_id": email.round_id,
            "round_number": email.round_number,
            "sent_at": email.sent_at,
            "response_due_at": email.response_due_at,
            "has_responded": response is not None,
            "classification": response.intent if response else None,
            "received_at": response.received_at if response else None,
        }

    def get_overdue_sent_candidate_ids(self, as_of: datetime) -> list[str]:
        """
        Candidate IDs sent an outreach email, past their response_due_at,
        with no reply on record - candidates for the auto-inactive job
        (services/threshold_evaluator.py).
        """
        rows = (
            self._db.query(Email.candidate_id)
            .outerjoin(CandidateResponse, CandidateResponse.email_id == Email.email_id)
            .filter(
                Email.status == STATUS_SENT,
                Email.response_due_at.isnot(None),
                Email.response_due_at < as_of,
                CandidateResponse.response_id.is_(None),
            )
            .all()
        )
        return [row.candidate_id for row in rows]

    def get_email_history_by_candidate_id(self, candidate_id: str) -> list[dict]:
        """
        Full email/response history for a candidate (GET
        /email/status/{candidate_id}/history).

        A candidate can have more than one Email row over time (a
        rejected/re-drafted attempt, an initial outreach followed by a
        next-round invitation, etc - candidate_id is indexed but not
        unique, see models.py), each with its own replies. Returns
        every email for this candidate plus every reply against each,
        oldest first overall.
        """
        emails = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id)
            .order_by(Email.created_at.asc())
            .all()
        )
        if not emails:
            return []

        history = []
        for email in emails:
            history.append(
                {
                    "event": "email_" + email.status.lower(),
                    "at": email.sent_at or email.approved_at or email.created_at,
                    "subject": email.subject,
                    "email_type": email.email_type,
                    "round_id": email.round_id,
                    "round_number": email.round_number,
                }
            )

            responses = (
                self._db.query(CandidateResponse)
                .filter(CandidateResponse.email_id == email.email_id)
                .order_by(CandidateResponse.received_at.asc())
                .all()
            )
            for response in responses:
                history.append(
                    {
                        "event": "reply_received",
                        "at": response.received_at,
                        "subject": response.subject,
                        "classification": response.intent,
                        "classification_source": response.classification_source,
                    }
                )

        return history

    def mark_inactive(self, candidate_id: str) -> None:
        """Auto-mark a non-responding candidate's outreach as Inactive."""
        email = (
            self._db.query(Email)
            .filter(Email.candidate_id == candidate_id, Email.status == STATUS_SENT)
            .first()
        )
        if not email:
            return

        email.status = STATUS_INACTIVE
        self._db.commit()
