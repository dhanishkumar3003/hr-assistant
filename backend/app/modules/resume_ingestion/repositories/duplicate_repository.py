"""
Module 1 - the ONLY class allowed to write the `duplicate_tracking` table.

APPEND-ONLY. There is deliberately no update or delete method: a diary that
can be edited stops being evidence.
"""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.resume_ingestion.models import DuplicateAction, DuplicateTracking, DuplicateType


class DuplicateWriteError(Exception):
    """The database refused the diary row (a CHECK rule, e.g. ck_dup_matched_something)."""


class IDuplicateRepository(ABC):
    @abstractmethod
    def record(
        self, *,
        duplicate_type: DuplicateType,
        action_taken: DuplicateAction,
        confidence: float | None,
        resume_id: int | None,
        candidate_id: int | None,
        matched_candidate_id: int | None,
        matched_resume_id: int | None,
        matched_embedding_id: int | None,
        detection_details: dict[str, Any],
        old_raw_profile_json: dict[str, Any] | None,
        new_raw_profile_json: dict[str, Any] | None,
    ) -> DuplicateTracking:
        """Write one diary row. At least one matched_* id must be given. Raises DuplicateWriteError."""


class DuplicateRepository(IDuplicateRepository):
    def __init__(self, db: Session):
        self._db = db

    def record(
        self, *,
        duplicate_type: DuplicateType,
        action_taken: DuplicateAction,
        confidence: float | None,
        resume_id: int | None,
        candidate_id: int | None,
        matched_candidate_id: int | None,
        matched_resume_id: int | None,
        matched_embedding_id: int | None,
        detection_details: dict[str, Any],
        old_raw_profile_json: dict[str, Any] | None,
        new_raw_profile_json: dict[str, Any] | None,
    ) -> DuplicateTracking:
        row = DuplicateTracking(
            duplicate_type=duplicate_type.value,
            action_taken=action_taken.value,
            duplicate_confidence=confidence,
            resume_id=resume_id,
            candidate_id=candidate_id,
            matched_candidate_id=matched_candidate_id,
            matched_resume_id=matched_resume_id,
            matched_embedding_id=matched_embedding_id,
            detection_details=detection_details,
            old_raw_profile_json=old_raw_profile_json,
            new_raw_profile_json=new_raw_profile_json,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DuplicateWriteError(str(exc.orig).strip().splitlines()[0]) from exc
        self._db.refresh(row)
        return row
