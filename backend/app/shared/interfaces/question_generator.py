from abc import ABC, abstractmethod
from uuid import UUID


class IQuestionGenerator(ABC):
    """Implemented separately by Module 4 (resume-based) and Module 5
    (difficulty-scaled technical). Both plug into the same interview flow controller.
    """

    @abstractmethod
    def generate(self, candidate_id: UUID) -> list[str]: ...