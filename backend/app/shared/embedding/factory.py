from functools import lru_cache

from app.core.config import settings
from app.shared.interfaces.embedding_service import IEmbeddingService
from app.shared.embedding.ollama_client import OllamaEmbeddingService


@lru_cache
def get_embedding_service() -> IEmbeddingService:
    """Single entry point every module uses to get an embedding client.
    Currently only 'ollama' is implemented. Add new providers as new classes
    in shared/embedding/ and register them here — never call a client class directly.
    """
    provider = settings.embedding_provider.lower()

    if provider == "ollama":
        return OllamaEmbeddingService()

    raise ValueError(f"Unknown EMBEDDING_PROVIDER '{provider}'. Supported: ollama")