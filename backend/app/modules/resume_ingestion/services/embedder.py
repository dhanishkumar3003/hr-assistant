"""
Module 1 - turning ONE candidate profile into ONE vector and storing it.

    profile_metadata (dict) --render--> embedding_text --embed--> vector
                                              |
                                           SHA-256 --> content_hash

Rules (see candidate_embeddings.sql):
  1. One active row per candidate. A changed profile deactivates the old row
     and inserts a new one; the old row is kept so a bad re-parse can be
     rolled back.
  2. Same hash + same model as the live row = the profile did not change =
     NO embedding call, NO new row. This is what makes re-uploads cheap.
  3. VECTOR(768) is married to nomic-embed-text; model_name is stored on every
     row so a model switch can never be mistaken for "unchanged".
  4. Text longer than the model can read is cut (with a warning) so a vector
     is never silently built from an input the model only half saw.
"""

import hashlib
import logging
from typing import Any

from app.modules.resume_ingestion.repositories.embedding_repository import IEmbeddingRepository
from app.modules.resume_ingestion.services.profile_text import render_profile_text
from app.shared.interfaces.embedding_service import IEmbeddingService

log = logging.getLogger(__name__)

MAX_TEXT_CHARS = 8000     # ~2,000 tokens - safely inside nomic-embed-text's context window
MIN_TEXT_CHARS = 20       # thinner than this = the LLM barely understood the resume; embed the raw words instead

#  What write() reports back.
EMBEDDED = "EMBEDDED"     # a new active row was written (the model was called)
UNCHANGED = "UNCHANGED"   # same text + same model as the live row: nothing done


class EmbeddingWriter:
    def __init__(
        self,
        repo: IEmbeddingRepository,
        embedding_service: IEmbeddingService,
        model_name: str,
        model_version: str | None = None,
        max_chars: int = MAX_TEXT_CHARS,
    ):
        self._repo = repo
        self._embedding = embedding_service
        self._model_name = model_name
        self._model_version = model_version
        self._max_chars = max_chars

    def write(
        self,
        candidate_id: int,
        resume_id: int,
        profile_metadata: dict[str, Any],
        fallback_text: str = "",
    ) -> str:
        """Make this candidate's live vector reflect `profile_metadata`. Returns EMBEDDED or UNCHANGED."""
        text = self._text_for(profile_metadata, fallback_text, resume_id)
        content_hash = sha256_text(text)

        current = self._repo.get_active_for_candidate(candidate_id)
        if (current is not None
                and current.content_hash == content_hash
                and current.model_name == self._model_name):
            log.info("candidate %s: profile unchanged (hash %s...) - embedding skipped",
                     candidate_id, content_hash[:12])
            return UNCHANGED

        #  The one AI call - made BEFORE touching the old row, so if the
        #  embedding service is down the candidate stays searchable as before.
        vector = self._embedding.embed(text)

        self._repo.deactivate_candidate(candidate_id)
        self._repo.add(
            candidate_id=candidate_id,
            resume_id=resume_id,
            profile_metadata=profile_metadata,
            embedding_text=text,
            embedding=vector,
            model_name=self._model_name,
            model_version=self._model_version,
            content_hash=content_hash,
        )
        return EMBEDDED

    def _text_for(self, metadata: dict[str, Any], fallback_text: str, resume_id: int) -> str:
        text = render_profile_text(metadata)
        if len(text) < MIN_TEXT_CHARS:
            #  Safety net: every candidate must be findable, even from a messy scan.
            text = fallback_text.strip() or text or str(metadata.get("name") or "").strip() or "profile"
        if len(text) > self._max_chars:
            log.warning("profile text of resume %s truncated to %d chars before embedding",
                        resume_id, self._max_chars)
            text = text[: self._max_chars]
        return text


def sha256_text(text: str) -> str:
    """SHA-256 hex of the UTF-8 text - the same thing as SQL's encode(sha256(convert_to(t,'UTF8')),'hex')."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
