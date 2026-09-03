"""
Module 1 - HTTP endpoints.

    router            mounted at /resumes     (main.py)
        POST /resumes/upload              one file      -> 202 + resume_id
        POST /resumes/bulk-upload         up to 20      -> 202 + accepted / rejected lists
        GET  /resumes/{resume_id}/status  poll for done -> 200

    candidates_router mounted at /candidates  (main.py)
        GET  /candidates/{candidate_id}   the full profile -> 200

This file is the COMPOSITION ROOT: the only place that knows the concrete
classes (ResumeRepository, LocalDiskStorage, LLMProfileExtractor, ...).
Everything below get_ingestion_service() / run_resume_processing() sees
interfaces only.
"""

from typing import NoReturn

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.db.session import SessionLocal
from app.modules.resume_ingestion.repositories.candidate_repository import CandidateRepository
from app.modules.resume_ingestion.repositories.duplicate_repository import DuplicateRepository
from app.modules.resume_ingestion.repositories.embedding_repository import EmbeddingRepository
from app.modules.resume_ingestion.repositories.resume_repository import ResumeRepository
from app.modules.resume_ingestion.repositories.search_repository import SearchRepository
from app.modules.resume_ingestion.schemas import (
    BulkUploadItem,
    BulkUploadRejected,
    BulkUploadResponse,
    CandidateListItem,
    CandidateListResponse,
    CandidateProfileResponse,
    ResumeStatusResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UploadAccepted,
)
from app.modules.resume_ingestion.services.duplicate_checker import TieredDuplicateDetector
from app.modules.resume_ingestion.services.embedder import EmbeddingWriter
from app.modules.resume_ingestion.services.ingestion_service import (
    DuplicateFileError,
    IngestionService,
    ResumeProcessingPipeline,
)
from app.modules.resume_ingestion.services.parser import default_registry
from app.modules.resume_ingestion.services.profile_extractor import LLMProfileExtractor
from app.modules.resume_ingestion.services.rules.email_rule import EmailRule
from app.modules.resume_ingestion.services.rules.phone_rule import PhoneRule
from app.modules.resume_ingestion.services.search_service import (
    EmbeddingUnavailableError,
    SearchQuery,
    SearchService,
)
from app.modules.resume_ingestion.services.storage import LocalDiskStorage
from app.modules.resume_ingestion.services.uploader import FileValidator, UploadValidationError
from app.shared.embedding.factory import get_embedding_service
from app.shared.llm.factory import get_llm_service

router = APIRouter()
candidates_router = APIRouter()

MAX_BULK_FILES = 20
ACCEPTED_MESSAGE = "File accepted. Processing takes about 60 seconds."


# ---------------------------------------------------------------------------
#  Wiring - concrete classes live here and nowhere else
# ---------------------------------------------------------------------------
def get_ingestion_service(db: Session = Depends(get_db)) -> IngestionService:
    return IngestionService(
        resume_repo=ResumeRepository(db),
        storage=LocalDiskStorage(),
        validator=FileValidator(),
        duplicate_repo=DuplicateRepository(db),
    )


def run_resume_processing(resume_id: int) -> None:
    """Background job. Runs after the response is sent, so the request's DB
    session is already closed - it must open (and close) its own."""
    db = SessionLocal()
    try:
        candidates = CandidateRepository(db)
        ResumeProcessingPipeline(
            resume_repo=ResumeRepository(db),
            candidate_repo=candidates,
            storage=LocalDiskStorage(),
            registry=default_registry(),
            profile_extractor=LLMProfileExtractor(get_llm_service()),   # Ollama, via the shared factory
            # Strongest signal first. To add SEMANTIC_MATCH later: one new rule class, one line here.
            detector=TieredDuplicateDetector([EmailRule(candidates), PhoneRule(candidates)]),
            duplicate_repo=DuplicateRepository(db),
            embedder=EmbeddingWriter(
                EmbeddingRepository(db), get_embedding_service(), model_name=settings.embedding_model
            ),
        ).run(resume_id)
    finally:
        db.close()


def _fail(status_code: int, error: str, message: str, **extra) -> NoReturn:
    """Every error has the same shape: {"detail": {"error": CODE, "message": "..."}}."""
    raise HTTPException(status_code=status_code, detail={"error": error, "message": message, **extra})


# ---------------------------------------------------------------------------
#  /resumes
# ---------------------------------------------------------------------------
@router.get("/ping")
def ping():
    return {"module": "resume_ingestion", "status": "ok"}


@router.post("/upload", response_model=UploadAccepted, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="pdf / docx / doc / txt, max 10 MB"),
    service: IngestionService = Depends(get_ingestion_service),
):
    content = await file.read()
    try:
        resume = service.accept(file.filename or "", content)
    except UploadValidationError as exc:
        _fail(exc.status_code, exc.error, exc.message)
    except DuplicateFileError as exc:
        _fail(
            status.HTTP_409_CONFLICT, "DUPLICATE_FILE", str(exc),
            matched_resume_id=exc.matched_resume_id,
            matched_candidate_id=exc.matched_candidate_id,
        )

    background.add_task(run_resume_processing, resume.resume_id)
    return UploadAccepted(
        resume_id=resume.resume_id,
        file_name=resume.file_name,
        processing_status=resume.processing_status,
        message=ACCEPTED_MESSAGE,
        status_url=f"/resumes/{resume.resume_id}/status",
    )


@router.post("/bulk-upload", response_model=BulkUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def bulk_upload(
    background: BackgroundTasks,
    files: list[UploadFile] = File(..., description="up to 20 files"),
    service: IngestionService = Depends(get_ingestion_service),
):
    if not files:
        _fail(status.HTTP_400_BAD_REQUEST, "NO_FILES", "No files were sent.")
    if len(files) > MAX_BULK_FILES:
        _fail(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "TOO_MANY_FILES",
              f"At most {MAX_BULK_FILES} files per request; you sent {len(files)}.")

    accepted: list[BulkUploadItem] = []
    rejected: list[BulkUploadRejected] = []

    # Each file is judged on its own - one bad file does not reject the batch.
    for upload in files:
        name = upload.filename or ""
        content = await upload.read()
        try:
            resume = service.accept(name, content)
        except UploadValidationError as exc:
            rejected.append(BulkUploadRejected(file_name=name, error=exc.error, message=exc.message))
            continue
        except DuplicateFileError as exc:
            rejected.append(BulkUploadRejected(file_name=name, error="DUPLICATE_FILE", message=str(exc)))
            continue

        background.add_task(run_resume_processing, resume.resume_id)
        accepted.append(BulkUploadItem(
            resume_id=resume.resume_id,
            file_name=resume.file_name,
            processing_status=resume.processing_status,
        ))

    return BulkUploadResponse(
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        accepted=accepted,
        rejected=rejected,
    )


@router.get("/{resume_id}/status", response_model=ResumeStatusResponse)
def resume_status(resume_id: int, db: Session = Depends(get_db)):
    resume = ResumeRepository(db).get_by_id(resume_id)
    if resume is None:
        _fail(status.HTTP_404_NOT_FOUND, "RESUME_NOT_FOUND", f"No resume with id {resume_id}.")
    return resume


# ---------------------------------------------------------------------------
#  /candidates
# ---------------------------------------------------------------------------
@candidates_router.post("/search", response_model=SearchResponse)
def search_candidates(payload: SearchRequest, db: Session = Depends(get_db)):
    """Search by MEANING. 'backend developer' finds a resume that only said 'Spring Boot'."""
    service = SearchService(SearchRepository(db), get_embedding_service())
    try:
        rows = service.search(SearchQuery(
            query=payload.query, top_k=payload.top_k, min_experience=payload.min_experience,
            skills=payload.skills, location=payload.location,
        ))
    except EmbeddingUnavailableError:
        _fail(status.HTTP_503_SERVICE_UNAVAILABLE, "EMBEDDING_SERVICE_UNAVAILABLE",
              "The embedding service (Ollama) is not reachable. Try again shortly.")

    # An empty results list is a normal 200, not an error.
    return SearchResponse(
        query=payload.query,
        result_count=len(rows),
        results=[
            SearchResultItem(
                candidate_id=r.candidate_id, name=r.name, current_job_title=r.current_job_title,
                current_company=r.current_company, experience_years=r.experience_years, skills=r.skills,
                similarity=round(r.similarity, 4),
                profile_text=r.profile_text, profile_metadata=r.profile_metadata,
            )
            for r in rows
        ],
    )


@candidates_router.get("", response_model=CandidateListResponse)
def list_candidates(
    db: Session = Depends(get_db),
    skills: str | None = Query(None, description="comma separated, must have ALL, e.g. Java,Docker"),
    min_experience: float | None = Query(None, ge=0),
    max_experience: float | None = Query(None, ge=0),
    location: str | None = None,
    job_title: str | None = None,
    is_active: bool = True,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Plain word filter - no meaning. Searching by meaning is POST /candidates/search."""
    if min_experience is not None and max_experience is not None and min_experience > max_experience:
        _fail(status.HTTP_400_BAD_REQUEST, "INVALID_FILTER", "min_experience is greater than max_experience.")

    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    total, items = SearchRepository(db).filter_candidates(
        skills=skill_list, min_experience=min_experience, max_experience=max_experience,
        location=location, job_title=job_title, is_active=is_active, limit=limit, offset=offset,
    )
    return CandidateListResponse(
        total=total, limit=limit, offset=offset,
        items=[CandidateListItem(**vars(row)) for row in items],
    )


@candidates_router.get("/{candidate_id}", response_model=CandidateProfileResponse)
def candidate_profile(candidate_id: int, db: Session = Depends(get_db)):
    candidate = CandidateRepository(db).get_by_id(candidate_id)
    if candidate is None:
        _fail(status.HTTP_404_NOT_FOUND, "CANDIDATE_NOT_FOUND", f"No candidate with id {candidate_id}.")
    return candidate
