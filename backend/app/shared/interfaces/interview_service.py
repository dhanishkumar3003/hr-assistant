from abc import ABC, abstractmethod
from uuid import UUID


class IInterviewService(ABC):
    """Implemented by Module 4 (voice) and Module 5 (technical).
    Consumed by Module 2 (trigger) and Module 6 (read results / Gate 1 & 2).
    """

    @abstractmethod
    def create_link(self, candidate_id: UUID) -> str:
        """Returns the secure interview URL/token to be emailed."""
        ...

    @abstractmethod
    def get_results(self, interview_id: UUID) -> dict:
        """Returns transcript + per-question and overall scores."""
        ...

    @abstractmethod
    def get_status(self, candidate_id: UUID) -> str:
        """Returns one of: not_started, started, in_progress, completed."""
        ...

    @abstractmethod
    def list_statuses(self) -> list[dict]:
        """Returns [{candidate_id, status, overall_score}, ...] for every
        candidate — powers the dashboard table. Per-question detail stays
        in get_results(), not here."""
        ...