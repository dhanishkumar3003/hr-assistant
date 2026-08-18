from abc import ABC, abstractmethod
from uuid import UUID

from app.shared.candidate_model import Candidate
from app.shared.enums import CandidateStatus


class ICandidateRepository(ABC):
    """Implemented by Module 1. Consumed by Modules 2, 3, 4, 5, 6."""

    @abstractmethod
    def get_by_id(self, candidate_id: UUID) -> Candidate | None: ...

    @abstractmethod
    def search(self, skills: list[str], min_experience: int) -> list[Candidate]: ...

    @abstractmethod
    def update_status(self, candidate_id: UUID, status: CandidateStatus) -> None: ...