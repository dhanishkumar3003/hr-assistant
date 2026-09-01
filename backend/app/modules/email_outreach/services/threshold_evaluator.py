"""
Response-threshold evaluation and auto-inactive marking.

Module 3 (PDD Section 5): "tracks whether each candidate replies within
a configurable threshold so the pipeline can automatically mark them
active or inactive." response_due_at is set at send time
(services/sender.py::send_approved_draft, using
settings.response_threshold_hours); this evaluates which sent-but-
unanswered candidates have crossed that deadline and marks them
Inactive. Depends only on IEmailRepository - run it from a scheduler
(cron/CLI) or on-demand via the API.
"""

import logging
from datetime import datetime, timezone

from app.modules.email_outreach.repositories.email_repository import IEmailRepository

log = logging.getLogger(__name__)


class ThresholdEvaluator:
    """Marks sent-but-unanswered candidates Inactive once past their response_due_at."""

    def __init__(self, email_repo: IEmailRepository):
        self._email_repo = email_repo

    def mark_overdue_inactive(self, as_of: datetime = None) -> list[str]:
        """
        Find every Sent candidate past their response_due_at with no
        reply on record, and mark them Inactive.

        Args:
            as_of (datetime): Evaluation timestamp; defaults to now
                (UTC). Exposed mainly for tests.

        Returns:
            list[str]: candidate_ids that were marked Inactive.
        """
        as_of = as_of or datetime.now(timezone.utc)
        overdue_candidate_ids = self._email_repo.get_overdue_sent_candidate_ids(as_of)

        for candidate_id in overdue_candidate_ids:
            self._email_repo.mark_inactive(candidate_id)
            log.info(f"Marked candidate inactive (no response by threshold) | candidate_id={candidate_id}")

        return overdue_candidate_ids
