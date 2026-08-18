from abc import ABC, abstractmethod
from uuid import UUID

from app.shared.enums import EmailPurpose


class IEmailService(ABC):
    """Implemented by Module 3. Consumed by Modules 2 and 6."""

    @abstractmethod
    def draft(self, candidate_ids: list[UUID], purpose: EmailPurpose) -> UUID:
        """Returns the draft ID, held pending HR approval."""
        ...

    @abstractmethod
    def approve_and_send(self, draft_id: UUID) -> None: ...

    @abstractmethod
    def get_status(self, candidate_id: UUID) -> str: ...