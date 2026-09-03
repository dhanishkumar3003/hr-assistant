"""
Module 1 - reading candidates for search and for the plain filter list.

Two kinds of query:
  * semantic_search - pgvector nearest-neighbour over candidate_embeddings,
    combined with the SQL filters. One active row per candidate, so
    LIMIT top_k really is the Top-K people. Each hit carries the JSONB
    profile, which is what Module 2 hands to the LLM (Top-K only, never all).
  * filter_candidates - a plain WHERE query, no vectors (API contract endpoint 5).

Read-only. Never writes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SearchRow:
    candidate_id: int
    name: str
    current_job_title: str | None
    current_company: str | None
    experience_years: float | None
    skills: list[Any]
    email: str | None
    similarity: float
    profile_text: str                    # embedding_text - the words the vector was built from (show HR WHY)
    profile_metadata: dict[str, Any]     # the JSONB profile - what Module 2 hands to the LLM


@dataclass(frozen=True)
class ListRow:
    candidate_id: int
    name: str
    current_job_title: str | None
    current_company: str | None
    current_location: str | None
    experience_years: float | None
    skills: list[Any]
    email: str | None


class ISearchRepository(ABC):
    @abstractmethod
    def semantic_search(
        self, *, query_vector: list[float], top_k: int,
        min_experience: float | None, skills: list[str] | None, location: str | None,
    ) -> list[SearchRow]: ...

    @abstractmethod
    def filter_candidates(
        self, *, skills: list[str] | None, min_experience: float | None, max_experience: float | None,
        location: str | None, job_title: str | None, is_active: bool, limit: int, offset: int,
    ) -> tuple[int, list[ListRow]]: ...


class SearchRepository(ISearchRepository):
    def __init__(self, db: Session):
        self._db = db

    # -----------------------------------------------------------------------
    #  Semantic search: filters narrow the pool, cosine distance ranks it.
    #  One active row per candidate -> no "best chunk" sub-query needed.
    #  WHERE e.is_active is REQUIRED or the partial HNSW index is skipped.
    # -----------------------------------------------------------------------
    def semantic_search(self, *, query_vector, top_k, min_experience, skills, location) -> list[SearchRow]:
        filters = ["e.is_active", "c.is_active"]
        params: dict[str, Any] = {"qvec": _vector_literal(query_vector), "top_k": top_k}

        if min_experience is not None:
            filters.append("c.experience_years >= :min_exp")
            params["min_exp"] = min_experience
        if location:
            filters.append("c.current_location ILIKE :loc")
            params["loc"] = f"%{location}%"
        if skills:
            filters.append("c.skills @> CAST(:skills AS jsonb)")
            params["skills"] = _json_array(skills)

        where = " AND ".join(filters)
        sql = text(f"""
            SELECT c.candidate_id, c.name, c.current_job_title, c.current_company,
                   c.experience_years, c.skills, c.email,
                   1 - (e.embedding <=> CAST(:qvec AS vector)) AS similarity,
                   e.embedding_text   AS profile_text,
                   e.profile_metadata
            FROM candidate_embeddings e
            JOIN candidates c ON c.candidate_id = e.candidate_id
            WHERE {where}
            ORDER BY e.embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
        """)
        rows = self._db.execute(sql, params).mappings().all()
        return [SearchRow(**{**r, "experience_years": _as_float(r["experience_years"])}) for r in rows]

    # -----------------------------------------------------------------------
    #  Plain filter list (no vectors) with a total count for pagination.
    # -----------------------------------------------------------------------
    def filter_candidates(self, *, skills, min_experience, max_experience, location,
                          job_title, is_active, limit, offset) -> tuple[int, list[ListRow]]:
        filters = ["is_active = :is_active"]
        params: dict[str, Any] = {"is_active": is_active}

        if skills:
            filters.append("skills @> CAST(:skills AS jsonb)")
            params["skills"] = _json_array(skills)
        if min_experience is not None:
            filters.append("experience_years >= :min_exp")
            params["min_exp"] = min_experience
        if max_experience is not None:
            filters.append("experience_years <= :max_exp")
            params["max_exp"] = max_experience
        if location:
            filters.append("current_location ILIKE :loc")
            params["loc"] = f"%{location}%"
        if job_title:
            filters.append("current_job_title ILIKE :title")
            params["title"] = f"%{job_title}%"

        where = " AND ".join(filters)
        total = self._db.execute(
            text(f"SELECT count(*) FROM candidates WHERE {where}"), params
        ).scalar_one()

        rows = self._db.execute(
            text(f"""
                SELECT candidate_id, name, current_job_title, current_company,
                       current_location, experience_years, skills, email
                FROM candidates WHERE {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """).bindparams(bindparam("limit"), bindparam("offset")),
            {**params, "limit": limit, "offset": offset},
        ).mappings().all()

        items = [ListRow(**{**r, "experience_years": _as_float(r["experience_years"])}) for r in rows]
        return total, items


def _vector_literal(vector: list[float]) -> str:
    """pgvector reads a vector from the text form '[0.1,0.2,...]'. Floats only - safe to inline."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _json_array(values: list[str]) -> str:
    import json
    return json.dumps(values)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None
