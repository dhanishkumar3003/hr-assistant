"""PHONE_MATCH - second identity signal. Runs only when the email rule found nobody."""

from app.modules.resume_ingestion.models import DuplicateType
from app.modules.resume_ingestion.repositories.candidate_repository import ICandidateRepository
from app.modules.resume_ingestion.services.duplicate_checker import (
    DuplicateVerdict,
    IDuplicateRule,
    IncomingProfile,
)


class PhoneRule(IDuplicateRule):
    def __init__(self, candidates: ICandidateRepository):
        self._candidates = candidates

    def check(self, incoming: IncomingProfile) -> DuplicateVerdict | None:
        if not incoming.phone:
            return None
        match = self._candidates.get_by_phone(incoming.phone)
        if match is None:
            return None
        return DuplicateVerdict(
            duplicate_type=DuplicateType.PHONE_MATCH,
            matched_candidate=match,
            confidence=1.0,
            details={"matched_on": "phone", "value": incoming.phone},
        )
