import httpx

from app.core.config import settings
from app.shared.interfaces.embedding_service import IEmbeddingService


class OllamaEmbeddingService(IEmbeddingService):
    def __init__(self):
        self._base_url = settings.ollama_base_url
        self._model = settings.embedding_model

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]