"""
Email sending operations for inviting candidates and confirming
their response.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.modules.email_outreach.repositories.email_repository import IEmailRepository
from app.modules.email_outreach.services.tracking_token_service import generate_token
from app.modules.email_outreach.services.email_builder import (
    build_response_message,
    build_prebuilt_message,
)
from app.modules.email_outreach.services.email_backend import get_email_backend
from app.modules.email_outreach.services.confirmation_content import get_confirmation_content

log = logging.getLogger(__name__)


class EmailSenderService:
    """
    Sends invitation and confirmation emails, and records them via the
    injected repository. Depends only on IEmailRepository - swap the
    concrete repository (or mock it in tests) without touching this
    class.
    """

    def __init__(self, email_repo: IEmailRepository, backend_name: str = None):
        self._email_repo = email_repo
        self._backend_name = backend_name

    def send_approved_draft(self, candidate_id: str) -> str:
        """
        Send a previously HR-approved draft (see services/drafter.py,
        services/approval_gate.py).

        Assigns the tracking token at send time (drafts are created
        before a token exists), appends it to the draft's subject, and
        sends the draft's stored body as-is - no re-rendering, so
        whatever HR approved (including any edits) is exactly what
        goes out.

        Args:
            candidate_id (str): Public candidate identifier.

        Returns:
            str: Tracking token if successful, None if no approved
                draft exists or sending failed.
        """
        draft = self._email_repo.get_draft_by_candidate_id(candidate_id)
        if not draft or draft["status"] != "Approved":
            return None

        token = generate_token()
        subject = f"{draft['subject']} [Ref:{token}]"

        message = build_prebuilt_message(
            draft["candidate_email"], subject, draft["body"], candidate_id
        )
        message_id = message["Message-ID"]

        if not get_email_backend(self._backend_name).send(message):
            return None

        sent_at = datetime.now(timezone.utc)
        response_due_at = sent_at + timedelta(hours=settings.response_threshold_hours)
        self._email_repo.mark_sent(candidate_id, token, sent_at, message_id, response_due_at)

        log.info(f"Sent approved draft | candidate_id={candidate_id} | token={token}")

        return token

    def send_confirmation(self, token: str, classification: str) -> bool:
        """
        Send a recruitment-response confirmation email for a
        classified reply.

        Called after a candidate's intent is settled by the email-reply
        classifier (services/reply_tracker.py / services/reply_classifier.py),
        via either the poll/Pub-Sub loop or POST /email/webhook/reply -
        both converge on ReplyTrackerService.process_reply(), which calls
        this. One place decides what a confirmation looks like and
        whether one goes out at all.

        Args:
            token (str): Tracking token.
            classification (str): Result from
                reply_classifier.classify_reply().

        Returns:
            bool: True if a confirmation was sent, or intentionally
                skipped for an unclassifiable reply. False if sending
                failed.
        """
        content = get_confirmation_content(classification)
        if content is None:
            log.info(
                f"No automated confirmation for "
                f"classification={classification} | token={token}"
            )
            return True

        record = self._email_repo.get_email_record(token)
        if not record:
            log.warning(f"send_confirmation called for unknown token={token}")
            return False

        context = {
            "candidate_name": record.get("candidate_name") or "",
            "company_name": record.get("company_name") or settings.company_name,
            "hr_name": record.get("hr_name") or "",
            "hr_designation": record.get("hr_designation") or "",
            "hr_email": record.get("hr_email") or "",
            **content,
        }

        message = build_response_message(
            record["candidate_email"], content["email_title"], context
        )

        if not get_email_backend(self._backend_name).send(message):
            log.error(f"Failed to send confirmation | token={token}")
            return False

        log.info(
            f"Sent confirmation | token={token} | classification={classification}"
        )
        return True
