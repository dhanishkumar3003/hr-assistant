"""
Module 1 - the ONLY class allowed to read or write `candidate_embeddings`.

One active row per candidate. Three operations: read the live row, retire it,
insert the new one. The search side lives in search_repository.py.
"""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.resume_ingestion.models import CandidateEmbedding


class EmbeddingWriteError(Exception):
    """The database refused the row (a CHECK or UNIQUE rule, e.g. a second active row)."""


class IEmbeddingRepository(ABC):
    @abstractmethod
    def get_active_for_candidate(self, candidate_id: int) -> CandidateEmbedding | None:
        """The candidate's live row (is_active = TRUE), or None if never embedded."""

    @abstractmethod
    def deactivate_candidate(self, candidate_id: int) -> int:
        """Set is_active = FALSE on the candidate's live row. Returns rows changed (0 or 1)."""

    @abstractmethod
    def add(
        self, *,
        candidate_id: int,
        resume_id: int,
        profile_metadata: dict[str, Any],
        embedding_text: str,
        embedding: list[float],
        model_name: str,
        model_version: str | None,
        content_hash: str,
    ) -> CandidateEmbedding:
        """Insert the new active row. Raises EmbeddingWriteError."""


class EmbeddingRepository(IEmbeddingRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_active_for_candidate(self, candidate_id: int) -> CandidateEmbedding | None:
        #  Served by the partial unique index ux_emb_candidate_active.
        return self._db.execute(
            select(CandidateEmbedding).where(
                CandidateEmbedding.candidate_id == candidate_id,
                CandidateEmbedding.is_active.is_(True),
            )
        ).scalar_one_or_none()

    def deactivate_candidate(self, candidate_id: int) -> int:
        result = self._db.execute(
            update(CandidateEmbedding)
            .where(CandidateEmbedding.candidate_id == candidate_id, CandidateEmbedding.is_active.is_(True))
            .values(is_active=False)
        )
        self._db.commit()
        return result.rowcount or 0

    def add(
        self, *,
        candidate_id: int,
        resume_id: int,
        profile_metadata: dict[str, Any],
        embedding_text: str,
        embedding: list[float],
        model_name: str,
        model_version: str | None,
        content_hash: str,
    ) -> CandidateEmbedding:
        row = CandidateEmbedding(
            candidate_id=candidate_id,
            resume_id=resume_id,
            profile_metadata=profile_metadata,
            embedding_text=embedding_text,
            embedding=embedding,
            model_name=model_name,
            model_version=model_version,
            content_hash=content_hash,
            is_active=True,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise EmbeddingWriteError(str(exc.orig).strip().splitlines()[0]) from exc
        self._db.refresh(row)
        return row
