from uuid import UUID
from app.shared.interfaces.question_generator import IQuestionGenerator

GENERIC_QUESTION_BANK = [
    "Tell me about a challenging bug you fixed recently.",
    "How do you approach learning a new technology?",
    "Describe a time you disagreed with a teammate's technical decision.",
]


class VoiceQuestionGenerator(IQuestionGenerator):
    """Module 4's question source: a fixed, generic bank.
    Deliberately NOT resume-based — see team discussion re: the
    IQuestionGenerator docstring conflict before changing this."""

    def generate(self, candidate_id: UUID) -> list[str]:
        return list(GENERIC_QUESTION_BANK)

    def get_question(self, index: int):
        if index < len(GENERIC_QUESTION_BANK):
            return GENERIC_QUESTION_BANK[index]
        return None

    def get_total(self) -> int:
        return len(GENERIC_QUESTION_BANK)