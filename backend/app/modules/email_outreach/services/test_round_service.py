"""
Business logic for sending the test-round assessment email.

Interim integration point: in the real flow, some other service will
generate the assessment link by calling an API with the candidate_id
and won't route the result through email at all. That link-generation
API doesn't exist yet, so this stands in for it - whoever has the link
just POSTs it here and this handles emailing it to the candidate.

Kept separate from the FastAPI route (api.py) so it can be unit tested
without spinning up the app.
"""

import logging

from app.core.config import settings
from app.modules.email_outreach.repositories.email_repository import IEmailRepository
from app.modules.email_outreach.services.candidate_source import (
    get_candidate_source,
    CandidateNotFoundError,
)
from app.modules.email_outreach.services.email_builder import build_test_round_message
from app.modules.email_outreach.services.email_backend import get_email_backend

log = logging.getLogger(__name__)


class TokenNotFoundError(Exception):
    """The candidate_id doesn't match any sent invitation."""


class TestRoundService:
    """Orchestrates the test-round assessment email. Depends only on abstractions."""

    def __init__(self, email_repo: IEmailRepository):
        self._email_repo = email_repo

    def send_test_round_email(self, candidate_id: str, round_id: str, url: str) -> None:
        """
        Email a candidate their assessment link.

        round_id alone is enough - the round's name, description,
        duration, deadline, and question count are resolved via
        services/candidate_source.py::fetch_round.

        Args:
            candidate_id (str): Public candidate identifier (see
                services/tracking_token_service.py).
            round_id (str): Test round identifier - looked up via the
                configured candidate source.
            url (str): The assessment/test link to send.

        Raises:
            TokenNotFoundError: If candidate_id is unknown.
            CandidateNotFoundError: If round_id is unknown.
            RuntimeError: If sending the email fails.
        """
        token = self._email_repo.get_token_by_candidate_id(candidate_id)
        if not token:
            raise TokenNotFoundError(candidate_id)

        record = self._email_repo.get_email_record(token)
        if not record:
            raise TokenNotFoundError(candidate_id)

        round_ = get_candidate_source().fetch_round(round_id)

        context = {
            "candidate_name": record.get("candidate_name") or "",
            "job_role": record.get("job_role") or "",
            "company_name": record.get("company_name") or settings.company_name,
            "hr_name": record.get("hr_name") or "",
            "hr_designation": record.get("hr_designation") or "",
            "hr_email": record.get("hr_email") or "",
            "test_link": url,
            "assessment_name": round_.get("round_name", ""),
            "round_description": round_.get("round_description", ""),
            "assessment_duration": round_.get("round_duration", ""),
            "assessment_deadline": round_.get("round_deadline", ""),
            "number_of_questions": round_.get("number_of_questions", ""),
        }

        message = build_test_round_message(
            record["candidate_email"], "Next Step: Complete Your Assessment", context
        )

        if not get_email_backend().send(message):
            raise RuntimeError(f"Failed to send test-round email for candidate_id={candidate_id}")

        self._email_repo.update_round(candidate_id, round_id, round_.get("round_number"))

        log.info(
            f"Sent test-round email | candidate_id={candidate_id} | "
            f"round_id={round_id} | round_number={round_.get('round_number')}"
        )
