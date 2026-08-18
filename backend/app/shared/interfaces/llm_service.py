from abc import ABC, abstractmethod


class ILLMService(ABC):
    """Implemented once (Anthropic client) in shared/llm/.
    Consumed by Module 2 (intent/query parsing), Module 4 (question gen + scoring),
    Module 5 (technical question gen + scoring).
    """

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...

    @abstractmethod
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Same as complete(), but instructs the model to return parsed JSON."""
        ...