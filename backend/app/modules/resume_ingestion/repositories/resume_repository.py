"""
Module 1 - the ONLY class allowed to read or write the `resumes` table.

Everything else (services, api) goes through IResumeRepository, so the
storage details can change without touching business logic (Dependency
Inversion), and so no other module ever writes to this table directly
(README golden rule).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.resume_ingestion.models import ProcessingStatus, Resume


class ResumeWriteError(Exception):
    """The database refused a write (a CHECK or UNIQUE rule). The message names the rule."""


class ResumeAlreadyStoredError(ResumeWriteError):
    """The database refused the insert because ux_resumes_file_hash already holds this hash."""


class IResumeRepository(ABC):
    @abstractmethod
    def get_by_id(self, resume_id: int) -> Resume | None: ...

    @abstractmethod
    def get_by_hash(self, file_hash: str) -> Resume | None: ...

    @abstractmethod
    def get_latest_for(self, candidate_id: int) -> Resume | None:
        """The row with is_latest = TRUE for this candidate, or None if they have no resume yet."""

    @abstractmethod
    def create(self, *, file_name: str, file_path: str, file_type: str,
               file_size_bytes: int, file_hash: str) -> Resume:
        """Insert a new UPLOADED row. Raises ResumeAlreadyStoredError on a duplicate hash."""

    @abstractmethod
    def mark_processing(self, resume_id: int) -> None: ...

    @abstractmethod
    def mark_extracted(self, resume_id: int, extracted_text: str) -> None: ...

    @abstractmethod
    def mark_failed(self, resume_id: int, reason: str) -> None: ...

    @abstractmethod
    def attach_to_candidate(self, resume_id: int, candidate_id: int) -> Resume:
        """Link a processed resume to its person: next version number, becomes the
        latest, status COMPLETED. One transaction. Raises ResumeWriteError."""


class ResumeRepository(IResumeRepository):
    def __init__(self, db: Session):
        self._db = db

    # ---- reads ----------------------------------------------------------
    def get_by_id(self, resume_id: int) -> Resume | None:
        return self._db.get(Resume, resume_id)

    def get_by_hash(self, file_hash: str) -> Resume | None:
        return self._db.execute(
            select(Resume).where(Resume.file_hash == file_hash)
        ).scalar_one_or_none()

    def get_latest_for(self, candidate_id: int) -> Resume | None:
        return self._db.execute(
            select(Resume).where(Resume.candidate_id == candidate_id, Resume.is_latest.is_(True))
        ).scalar_one_or_none()          # ux_resumes_one_latest guarantees at most one

    # ---- writes ---------------------------------------------------------
    def create(self, *, file_name: str, file_path: str, file_type: str,
               file_size_bytes: int, file_hash: str) -> Resume:
        resume = Resume(
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            file_hash=file_hash,
            # candidate_id / resume_version stay NULL until the AI has read the file.
            # processing_status defaults to UPLOADED in the database.
        )
        self._db.add(resume)
        try:
            self._db.commit()
        except IntegrityError as exc:
            # Two uploads of the same bytes raced each other; the unique index won.
            self._db.rollback()
            raise ResumeAlreadyStoredError(file_hash) from exc
        self._db.refresh(resume)          # pull back the id, defaults and timestamps
        return resume

    def mark_processing(self, resume_id: int) -> None:
        self._set_status(resume_id, ProcessingStatus.PROCESSING)

    def mark_extracted(self, resume_id: int, extracted_text: str) -> None:
        self._set_status(resume_id, ProcessingStatus.EXTRACTED, extracted_text=extracted_text)

    def mark_failed(self, resume_id: int, reason: str) -> None:
        # ck_resumes_failed_has_reason: FAILED without a reason is refused by the DB.
        self._set_status(
            resume_id, ProcessingStatus.FAILED,
            failure_reason=reason, processed_at=datetime.now(timezone.utc),
        )

    def attach_to_candidate(self, resume_id: int, candidate_id: int) -> Resume:
        resume = self._db.get(Resume, resume_id)
        if resume is None:
            raise ResumeWriteError(f"resume {resume_id} not found")

        latest_version = self._db.execute(
            select(func.max(Resume.resume_version)).where(Resume.candidate_id == candidate_id)
        ).scalar()

        try:
            # ux_resumes_one_latest allows ONE latest per candidate: switch the old
            # one OFF before the new one goes ON, inside the same transaction.
            self._db.execute(
                update(Resume)
                .where(Resume.candidate_id == candidate_id, Resume.is_latest.is_(True))
                .values(is_latest=False)
            )
            resume.candidate_id = candidate_id
            resume.resume_version = (latest_version or 0) + 1      # set together: ck_resumes_version_with_candidate
            resume.is_latest = True
            resume.processing_status = ProcessingStatus.COMPLETED.value
            resume.processed_at = datetime.now(timezone.utc)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ResumeWriteError(str(exc.orig).strip().splitlines()[0]) from exc

        self._db.refresh(resume)
        return resume

    def _set_status(self, resume_id: int, status: ProcessingStatus, **fields) -> None:
        resume = self._db.get(Resume, resume_id)
        if resume is None:
            return
        resume.processing_status = status.value
        for name, value in fields.items():
            setattr(resume, name, value)
        self._db.commit()
