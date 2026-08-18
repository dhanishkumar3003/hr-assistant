from abc import ABC, abstractmethod


class IEmbeddingService(ABC):
    """Implemented once (Ollama/Nomic client) in shared/embedding/.
    Consumed by Module 1 (resume embeddings) and Module 2 (query embeddings for search).
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...