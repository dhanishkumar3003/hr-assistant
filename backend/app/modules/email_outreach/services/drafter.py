"""
Draft generation for outreach emails.

Builds an email body/subject for a candidate and round, and holds it
as a pending Draft via the repository - nothing is sent until
services/approval_gate.py records HR approval.
"""

import logging

from app.core.config import settings
from app.modules.email_outreach.repositories.email_repository import (
    IEmailRepository,
    EMAIL_TYPE_INTERVIEW_INVITATION,
    EMAIL_TYPE_NEXT_ROUND_INVITATION,
    EMAIL_TYPE_CANDIDATE_REJECTION,
)
from app.modules.email_outreach.services.candidate_source import get_candidate_source
from app.modules.email_outreach.services.email_template_service import (
    render_invite_html,
    render_rejection_html,
)
from app.modules.email_outreach.services.rejection_drafter import generate_rejection_paragraph

log = logging.getLogger(__name__)

# round_type (app/tests/modules/email_outreach/testdata.json's rounds[] catalog) ->
# email_type stored on the Email row. "assessment" rounds don't go
# through this drafter at all - they're sent directly by
# services/test_round_service.py against email_round_test.html, no
# draft/approval step.
_EMAIL_TYPE_BY_ROUND_TYPE = {
    "invitation": EMAIL_TYPE_INTERVIEW_INVITATION,
    "next_round": EMAIL_TYPE_NEXT_ROUND_INVITATION,
    "rejection": EMAIL_TYPE_CANDIDATE_REJECTION,
}

_SUBJECT_BY_ROUND_TYPE = {
    "invitation": "Interview Invitation",
    "next_round": "Next Round Invitation",
    "rejection": "Application Update",
}


class DraftAlreadyExistsError(Exception):
    """A pending or approved draft already exists for this candidate."""


class UnsupportedRoundTypeError(Exception):
    """This round's round_type has no drafter template (e.g. "assessment" - see services/test_round_service.py)."""


class EmailDrafter:
    """
    Generates an outreach email draft for a candidate and stores it as
    pending HR approval. Depends only on IEmailRepository.
    """

    def __init__(self, email_repo: IEmailRepository):
        self._email_repo = email_repo

    def create_draft(self, candidate_id: str, round_id: str) -> dict:
        """
        Draft an outreach email for one candidate and round.

        candidate_id + round_id alone are enough - the candidate's
        email/name, the job/HR details their record points to
        (job_id/hr_id), and the round's name/type/number are all
        resolved via services/candidate_source.py.

        Args:
            candidate_id (str): Public candidate identifier - looked
                up via the configured candidate source.
            round_id (str): Round identifier from the rounds[] catalog
                (app/tests/modules/email_outreach/testdata.json) - its round_type
                (invitation/next_round/rejection) selects the template
                and subject line; its round_number is stored on the
                Email row for progress tracking (GET /email/status).

        Returns:
            dict: The stored draft (subject, body, status="Draft",
                round_id, round_number).

        Raises:
            DraftAlreadyExistsError: A pending/approved draft already
                exists for this candidate_id.
            CandidateNotFoundError: candidate_id/round_id (or the
                job_id/hr_id the candidate references) doesn't resolve
                to a record.
            UnsupportedRoundTypeError: round_id's round_type is
                "assessment" - those are sent via POST /email/test-round,
                not drafted/approved here.
        """
        if self._email_repo.get_draft_by_candidate_id(candidate_id):
            raise DraftAlreadyExistsError(candidate_id)

        round_ = get_candidate_source().fetch_round(round_id)
        round_type = round_.get("round_type")
        round_number = round_.get("round_number")

        email_type = _EMAIL_TYPE_BY_ROUND_TYPE.get(round_type)
        if email_type is None:
            raise UnsupportedRoundTypeError(
                f"round_id={round_id} has round_type={round_type!r} - "
                "use POST /email/test-round for assessment rounds"
            )

        resolved = get_candidate_source().build_template_context(candidate_id)
        candidate_email = resolved["email"]
        candidate_name = resolved.get("name", "")

        context = {
            "candidate_name": candidate_name,
            **resolved,
            "company_name": settings.company_name,
        }
        job_role = context.get("job_role")
        subject_prefix = round_.get("round_name") or _SUBJECT_BY_ROUND_TYPE.get(
            round_type, "Interview Invitation"
        )
        subject = f"{subject_prefix}{f' - {job_role}' if job_role else ''}"

        if round_type == "rejection":
            context["decision_paragraph"] = generate_rejection_paragraph(
                candidate_name, job_role, context.get("company_name")
            )
            body = render_rejection_html(context)
        else:
            body = render_invite_html(context)

        self._email_repo.save_draft(
            candidate_id=candidate_id,
            candidate_email=candidate_email,
            candidate_name=candidate_name,
            subject=subject,
            body=body,
            email_type=email_type,
            template_context=context,
            round_id=round_id,
            round_number=round_number,
        )

        log.info(
            f"Drafted outreach email | candidate_id={candidate_id} | "
            f"round_id={round_id} | round_number={round_number}"
        )

        return self._email_repo.get_draft_by_candidate_id(candidate_id)
