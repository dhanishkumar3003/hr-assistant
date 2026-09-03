"""EMAIL_MATCH - the strongest identity signal we have. Email is unique per candidate."""

from app.modules.resume_ingestion.models import DuplicateType
from app.modules.resume_ingestion.repositories.candidate_repository import ICandidateRepository
from app.modules.resume_ingestion.services.duplicate_checker import (
    DuplicateVerdict,
    IDuplicateRule,
    IncomingProfile,
)


class EmailRule(IDuplicateRule):
    def __init__(self, candidates: ICandidateRepository):
        self._candidates = candidates

    def check(self, incoming: IncomingProfile) -> DuplicateVerdict | None:
        if not incoming.email:
            return None
        match = self._candidates.get_by_email(incoming.email)
        if match is None:
            return None
        return DuplicateVerdict(
            duplicate_type=DuplicateType.EMAIL_MATCH,
            matched_candidate=match,
            confidence=1.0,
            details={"matched_on": "email", "value": incoming.email},
        )
