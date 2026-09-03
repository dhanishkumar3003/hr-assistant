"""
Module 1 - request / response shapes for the HTTP layer.

These mirror  docs/api-contracts/resume_ingestion.md  (v0.2) exactly.
Change the contract first, then this file - never the other way round.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
#  POST /resumes/upload  ->  202
# ---------------------------------------------------------------------------
class UploadAccepted(BaseModel):
    resume_id: int
    file_name: str
    processing_status: str
    message: str
    status_url: str


# ---------------------------------------------------------------------------
#  POST /resumes/bulk-upload  ->  202
# ---------------------------------------------------------------------------
class BulkUploadItem(BaseModel):
    resume_id: int
    file_name: str
    processing_status: str


class BulkUploadRejected(BaseModel):
    file_name: str
    error: str
    message: str


class BulkUploadResponse(BaseModel):
    accepted_count: int
    rejected_count: int
    accepted: list[BulkUploadItem]
    rejected: list[BulkUploadRejected]


# ---------------------------------------------------------------------------
#  GET /resumes/{resume_id}/status  ->  200
#  Only trust candidate_id when processing_status == "COMPLETED".
# ---------------------------------------------------------------------------
class ResumeStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # build straight from the Resume ORM row

    resume_id: int
    file_name: str
    processing_status: str
    candidate_id: int | None
    resume_version: int | None
    is_latest: bool
    failure_reason: str | None
    created_at: datetime
    processed_at: datetime | None


# ---------------------------------------------------------------------------
#  GET /candidates/{candidate_id}  ->  200
#  skills / education / experience / certifications are ALWAYS arrays (maybe empty).
#  Everything else marked "| None" can be null - the AI does not always find it.
# ---------------------------------------------------------------------------
class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # built straight from the Candidate ORM row

    candidate_id: int
    name: str
    email: str | None
    phone: str | None
    current_location: str | None
    current_job_title: str | None
    current_company: str | None
    experience_years: float | None
    skills: list[Any]
    education: list[Any]
    experience: list[Any]
    certifications: list[Any]
    linkedin_url: str | None
    extraction_confidence: float | None
    is_active: bool
    resume_count: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
#  GET /candidates?skills=&min_experience=...  ->  200   (plain filter list)
# ---------------------------------------------------------------------------
class CandidateListItem(BaseModel):
    candidate_id: int
    name: str
    current_job_title: str | None
    current_company: str | None
    current_location: str | None
    experience_years: float | None
    skills: list[Any]
    email: str | None


class CandidateListResponse(BaseModel):
    total: int                 # count BEFORE limit - use it for paging
    limit: int
    offset: int
    items: list[CandidateListItem]


# ---------------------------------------------------------------------------
#  POST /candidates/search  ->  200   (search by meaning)
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=50)
    min_experience: float | None = None
    skills: list[str] | None = None
    location: str | None = None


class SearchResultItem(BaseModel):
    candidate_id: int
    name: str
    current_job_title: str | None
    current_company: str | None
    experience_years: float | None
    skills: list[Any]
    similarity: float                 # 0.0 - 1.0, higher is better
    profile_text: str                 # the words the vector was built from - show it, so HR sees WHY
    profile_metadata: dict[str, Any]  # the JSONB profile - what Module 2 sends to the LLM (Top-K only)


class SearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[SearchResultItem]


# ---------------------------------------------------------------------------
#  Every error, every endpoint:  {"detail": {"error": CODE, "message": "..."}}
#  Callers branch on `error`, never on `message`.
# ---------------------------------------------------------------------------
class ErrorBody(BaseModel):
    error: str
    message: str
