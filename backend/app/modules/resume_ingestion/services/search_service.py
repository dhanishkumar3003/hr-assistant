"""
Module 1 - the search brain behind POST /candidates/search.

Embeds the query with the SAME model used for the chunks, hands the vector to
the repository, returns ranked candidates. An empty result list is a normal
answer, not an error.
"""

from dataclasses import dataclass

from app.modules.resume_ingestion.repositories.search_repository import ISearchRepository, SearchRow
from app.shared.interfaces.embedding_service import IEmbeddingService


class EmbeddingUnavailableError(Exception):
    """The embedding service (Ollama) could not be reached. Becomes a 503."""


@dataclass(frozen=True)
class SearchQuery:
    query: str
    top_k: int = 10
    min_experience: float | None = None
    skills: list[str] | None = None
    location: str | None = None


class SearchService:
    def __init__(self, search_repo: ISearchRepository, embedding_service: IEmbeddingService):
        self._repo = search_repo
        self._embedding = embedding_service

    def search(self, request: SearchQuery) -> list[SearchRow]:
        try:
            query_vector = self._embedding.embed(request.query)
        except Exception as exc:   # noqa: BLE001 - Ollama down, timeout, etc.
            raise EmbeddingUnavailableError(str(exc)) from exc

        return self._repo.semantic_search(
            query_vector=query_vector,
            top_k=request.top_k,
            min_experience=request.min_experience,
            skills=request.skills,
            location=request.location,
        )
