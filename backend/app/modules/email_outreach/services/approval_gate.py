"""
HR approval gate for pending email drafts.

Sits between drafting (services/drafter.py) and sending
(services/sender.py::send_approved_draft) - nothing reaches
send_approved_draft without going through here first.
"""

import logging

from app.modules.email_outreach.repositories.email_repository import IEmailRepository
from app.modules.email_outreach.services.candidate_source import get_candidate_source

log = logging.getLogger(__name__)


class DraftNotFoundError(Exception):
    """No pending draft exists for this candidate_id."""


class ApprovalGate:
    """
    Approves or rejects a pending draft. Depends only on
    IEmailRepository - the actual send happens elsewhere
    (services/sender.py), triggered only after approve() succeeds.
    """

    def __init__(self, email_repo: IEmailRepository):
        self._email_repo = email_repo

    def approve(
        self, candidate_id: str, approved_by_hr_id: str = None, edited_body: str = None
    ) -> dict:
        """
        Approve a pending draft, optionally with HR edits to the body.

        Args:
            candidate_id (str): Public candidate identifier.
            approved_by_hr_id (str): hr_id of the approving HR user -
                resolved via services/candidate_source.py::fetch_hr and
                stored as their name (matches the candidate/job/round
                id-only pattern used elsewhere in this module).
            edited_body (str): If HR edited the draft body before
                approving, the replacement HTML body; None keeps the
                drafted body as-is.

        Returns:
            dict: The approved draft record.

        Raises:
            DraftNotFoundError: No pending draft exists for candidate_id.
            CandidateNotFoundError: approved_by_hr_id doesn't resolve
                to a known HR record.
        """
        draft = self._email_repo.get_draft_by_candidate_id(candidate_id)
        if not draft or draft["status"] != "Draft":
            raise DraftNotFoundError(candidate_id)

        approved_by = None
        if approved_by_hr_id:
            hr = get_candidate_source().fetch_hr(approved_by_hr_id)
            approved_by = hr.get("name", approved_by_hr_id)

        self._email_repo.approve_draft(candidate_id, approved_by, edited_body)
        log.info(
            f"Draft approved | candidate_id={candidate_id} | "
            f"approved_by_hr_id={approved_by_hr_id} | approved_by={approved_by}"
        )

        return self._email_repo.get_draft_by_candidate_id(candidate_id)

    def reject(self, candidate_id: str) -> None:
        """
        Reject a pending draft - it will never be sent.

        Args:
            candidate_id (str): Public candidate identifier.

        Raises:
            DraftNotFoundError: No pending draft exists for candidate_id.
        """
        draft = self._email_repo.get_draft_by_candidate_id(candidate_id)
        if not draft or draft["status"] != "Draft":
            raise DraftNotFoundError(candidate_id)

        self._email_repo.reject_draft(candidate_id)
        log.info(f"Draft rejected | candidate_id={candidate_id}")
