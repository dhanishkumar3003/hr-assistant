"""
Module 1 - the two orchestrators.

IngestionService          runs INSIDE the HTTP request : validate -> hash ->
                          exact-file check -> store file -> insert resumes row.
                          Returns in well under a second.

ResumeProcessingPipeline  runs AFTER the response is sent (FastAPI background
                          task) : read file -> extract text -> LLM builds the
                          profile -> "seen this person?" -> new candidate, or
                          next resume version of the existing one (+ diary row).

      UPLOADED -> PROCESSING -> EXTRACTED -> COMPLETED      (or FAILED + reason)

Both depend only on interfaces. The concrete classes are wired together in
api.py - nowhere else.
"""

import logging
from typing import Any

from app.modules.resume_ingestion.models import DuplicateAction, DuplicateType, Resume
from app.modules.resume_ingestion.repositories.candidate_repository import (
    CandidateAlreadyExistsError,
    CandidateWriteError,
    ICandidateRepository,
)
from app.modules.resume_ingestion.repositories.duplicate_repository import (
    DuplicateWriteError,
    IDuplicateRepository,
)
from app.modules.resume_ingestion.repositories.resume_repository import (
    IResumeRepository,
    ResumeAlreadyStoredError,
    ResumeWriteError,
)
from app.modules.resume_ingestion.services.duplicate_checker import (
    DuplicateVerdict,
    IncomingProfile,
    TieredDuplicateDetector,
)
from app.modules.resume_ingestion.services.embedder import EmbeddingWriter
from app.modules.resume_ingestion.services.normalizer import normalize_email, normalize_phone
from app.modules.resume_ingestion.services.parser import ExtractorRegistry, TextExtractionError
from app.modules.resume_ingestion.services.profile_extractor import (
    ExtractedProfile,
    IProfileExtractor,
    ProfileExtractionError,
)
from app.modules.resume_ingestion.services.profile_text import build_profile_metadata
from app.modules.resume_ingestion.services.profile_merger import merge_profile, profile_changed, snapshot
from app.modules.resume_ingestion.services.storage import IFileStorage
from app.modules.resume_ingestion.services.uploader import FileValidator, ValidatedUpload

log = logging.getLogger(__name__)


class DuplicateFileError(Exception):
    """The identical file (same SHA-256) is already stored. Becomes a 409 DUPLICATE_FILE."""

    def __init__(self, matched_resume_id: int, matched_candidate_id: int | None):
        super().__init__("This exact file was already uploaded.")
        self.matched_resume_id = matched_resume_id
        self.matched_candidate_id = matched_candidate_id


# ===========================================================================
#  In the request
# ===========================================================================
class IngestionService:
    def __init__(
        self,
        resume_repo: IResumeRepository,
        storage: IFileStorage,
        validator: FileValidator,
        duplicate_repo: IDuplicateRepository,
    ):
        self._repo = resume_repo
        self._storage = storage
        self._validator = validator
        self._diary = duplicate_repo

    def accept(self, file_name: str, content: bytes) -> Resume:
        """
        Accept one upload. Raises UploadValidationError (bad file) or
        DuplicateFileError (seen before). Returns the new UPLOADED row.
        """
        upload = self._validator.validate(file_name, content)

        # Cheap check first so HR gets a clear 409 instead of a database error,
        # and so a byte-identical file never costs disk space or an LLM call.
        existing = self._repo.get_by_hash(upload.sha256)
        if existing is not None:
            self._record_rejection(upload, existing)
            raise DuplicateFileError(existing.resume_id, existing.candidate_id)

        file_path = self._storage.save(upload.content, upload.file_type)
        try:
            return self._repo.create(
                file_name=upload.file_name,
                file_path=file_path,
                file_type=upload.file_type,
                file_size_bytes=upload.size_bytes,
                file_hash=upload.sha256,
            )
        except ResumeAlreadyStoredError:
            # Lost a race with a simultaneous upload of the same bytes: the
            # unique index caught it. Remove our copy and report the winner.
            self._storage.delete(file_path)
            winner = self._repo.get_by_hash(upload.sha256)
            if winner is not None:
                self._record_rejection(upload, winner)
            raise DuplicateFileError(
                winner.resume_id if winner else -1,
                winner.candidate_id if winner else None,
            )

    def _record_rejection(self, upload: ValidatedUpload, existing: Resume) -> None:
        """EXACT_FILE_MATCH diary row. Evidence only - a failure here must not block the 409."""
        try:
            self._diary.record(
                duplicate_type=DuplicateType.EXACT_FILE_MATCH,
                action_taken=DuplicateAction.DUPLICATE_REJECTED,
                confidence=1.0,
                resume_id=None,                      # never stored: rejected on arrival
                candidate_id=None,
                matched_candidate_id=existing.candidate_id,
                matched_resume_id=existing.resume_id,
                matched_embedding_id=None,
                detection_details={"matched_on": "file_hash", "file_name": upload.file_name,
                                   "value": upload.sha256},
                old_raw_profile_json=None,
                new_raw_profile_json=None,
            )
        except DuplicateWriteError as exc:
            log.warning("duplicate_tracking row not written for rejected upload %s: %s", upload.file_name, exc)


# ===========================================================================
#  In the background
# ===========================================================================
class ResumeProcessingPipeline:
    def __init__(
        self,
        resume_repo: IResumeRepository,
        candidate_repo: ICandidateRepository,
        storage: IFileStorage,
        registry: ExtractorRegistry,
        profile_extractor: IProfileExtractor,
        detector: TieredDuplicateDetector,
        duplicate_repo: IDuplicateRepository,
        embedder: EmbeddingWriter,
    ):
        self._resumes = resume_repo
        self._candidates = candidate_repo
        self._storage = storage
        self._registry = registry
        self._extractor = profile_extractor
        self._detector = detector
        self._diary = duplicate_repo
        self._embedder = embedder

    def run(self, resume_id: int) -> None:
        resume = self._resumes.get_by_id(resume_id)
        if resume is None:
            return

        self._resumes.mark_processing(resume_id)

        text = self._extract_text(resume)
        if text is None:                       # already marked FAILED with a reason
            return
        self._resumes.mark_extracted(resume_id, text)

        self._build_profile(resume_id, text)

    # ---- step 1: file -> text ---------------------------------------------
    def _extract_text(self, resume: Resume) -> str | None:
        extractor = self._registry.for_type(resume.file_type)
        if extractor is None:
            self._resumes.mark_failed(
                resume.resume_id,
                f"No text extractor for '.{resume.file_type}' files - please convert to .docx or .pdf and upload again",
            )
            return None

        try:
            text = extractor.extract(self._storage.get(resume.file_path))
        except TextExtractionError as exc:
            self._resumes.mark_failed(resume.resume_id, str(exc))
            return None
        except Exception as exc:   # noqa: BLE001 - a background task must never die silently
            self._resumes.mark_failed(
                resume.resume_id, f"Unexpected error during text extraction: {type(exc).__name__}: {exc}"
            )
            return None

        if not text:
            self._resumes.mark_failed(resume.resume_id, "No text could be extracted - the file may be a scanned image")
            return None
        return text

    # ---- step 2: text -> profile -> person ---------------------------------
    def _build_profile(self, resume_id: int, text: str) -> None:
        try:
            profile, raw = self._extractor.extract(text)
        except ProfileExtractionError as exc:
            self._resumes.mark_failed(resume_id, str(exc))
            return
        except Exception as exc:   # noqa: BLE001
            self._resumes.mark_failed(
                resume_id, f"Unexpected error during profile extraction: {type(exc).__name__}: {exc}"
            )
            return

        if not profile.name:                   # candidates.name is NOT NULL - never guess a name
            self._resumes.mark_failed(resume_id, "No candidate name found in the resume text")
            return

        columns = self._columns_from(profile, normalize_email(profile.email), normalize_phone(profile.phone), raw)

        try:
            verdict = self._detector.detect(IncomingProfile(email=columns["email"], phone=columns["phone"]))
            if verdict is None:
                candidate_id = self._create_new_person(resume_id, columns)
            else:
                candidate_id = self._append_to_existing_person(resume_id, verdict, columns)
        except (CandidateWriteError, ResumeWriteError) as exc:
            self._resumes.mark_failed(resume_id, f"Database refused the profile: {exc}")
            return

        # The resume is COMPLETED at this point. Embedding is best-effort: if the
        # embedding service is down the candidate still exists, just not searchable
        # yet. Do not fail the resume over it - log and move on.
        self._embed(candidate_id, resume_id, text)

    def _embed(self, candidate_id: int, resume_id: int, resume_text: str) -> None:
        """The candidate row AS IT NOW STANDS (merged, if this was a re-upload) -> one JSON -> one vector."""
        try:
            candidate = self._candidates.get_by_id(candidate_id)
            profile_metadata = build_profile_metadata(candidate)
            self._embedder.write(candidate_id, resume_id, profile_metadata, fallback_text=resume_text)
        except Exception as exc:   # noqa: BLE001
            log.warning("embedding failed for resume %s (candidate %s): %s", resume_id, candidate_id, exc)

    def _create_new_person(self, resume_id: int, columns: dict[str, Any]) -> int:
        try:
            candidate = self._candidates.create(**columns)
        except CandidateAlreadyExistsError:
            # Two resumes of the same person were processed at the same moment and the
            # other one won the unique index. Look again - it is a duplicate after all.
            verdict = self._detector.detect(IncomingProfile(email=columns["email"], phone=columns["phone"]))
            if verdict is None:
                raise
            return self._append_to_existing_person(resume_id, verdict, columns)
        self._resumes.attach_to_candidate(resume_id, candidate.candidate_id)
        return candidate.candidate_id

    def _append_to_existing_person(self, resume_id: int, verdict: DuplicateVerdict, columns: dict[str, Any]) -> int:
        candidate = verdict.matched_candidate
        before = snapshot(candidate)                          # the undo button, taken FIRST
        merged = merge_profile(before, columns)               # newer wins, blanks never erase
        changed = profile_changed(before, merged)
        previous_latest = self._resumes.get_latest_for(candidate.candidate_id)

        if changed:
            self._candidates.update_profile(candidate.candidate_id, **merged)
        self._resumes.attach_to_candidate(resume_id, candidate.candidate_id)   # becomes version N+1, latest

        self._record_append(resume_id, verdict, candidate, before, merged, changed, previous_latest)
        return candidate.candidate_id

    def _record_append(self, resume_id, verdict, candidate, before, merged, changed, previous_latest) -> None:
        try:
            self._diary.record(
                duplicate_type=verdict.duplicate_type,
                action_taken=DuplicateAction.PROFILE_UPDATED if changed else DuplicateAction.RESUME_APPENDED,
                confidence=verdict.confidence,
                resume_id=resume_id,
                candidate_id=candidate.candidate_id,
                matched_candidate_id=candidate.candidate_id,
                matched_resume_id=previous_latest.resume_id if previous_latest else None,
                matched_embedding_id=None,
                detection_details=verdict.details,
                old_raw_profile_json=before["raw_profile_json"],
                new_raw_profile_json=merged["raw_profile_json"],
            )
        except DuplicateWriteError as exc:
            log.warning("duplicate_tracking row not written for resume %s: %s", resume_id, exc)

    @staticmethod
    def _columns_from(profile: ExtractedProfile, email: str | None, phone: str | None,
                      raw: dict[str, Any]) -> dict[str, Any]:
        """The 13 known fields -> candidates columns. Everything the LLM said -> raw_profile_json."""
        return dict(
            name=profile.name,
            email=email,
            phone=phone,
            current_location=profile.current_location,
            current_job_title=profile.current_job_title,
            current_company=profile.current_company,
            experience_years=profile.experience_years,
            skills=profile.skills,
            education=profile.education,
            experience=profile.experience,
            certifications=profile.certifications,
            linkedin_url=profile.linkedin_url,
            extraction_confidence=profile.extraction_confidence,
            raw_profile_json=raw,
        )
