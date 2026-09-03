"""
Module 1 - Resume Repository & Ingestion : database models.

One Python class per table. These four classes are the Python twin of the
four SQL files in  backend/app/db/sql/module1/ :

    Candidate           <->  candidates.sql            (the PERSON)
    Resume              <->  resumes.sql               (the FILES)
    CandidateEmbedding  <->  candidate_embeddings.sql  (the MEANING)
    DuplicateTracking   <->  duplicate_tracking.sql    (the DIARY)

If a column is changed here it must ALSO be changed in a new Alembic
migration - editing this file alone does nothing to the real database
(see README section 8).

Owner : Monish (MOD-01)
Rev   : 2026-08-25 - integer ids (BIGSERIAL), simplified column set.
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ============================================================================
#  Allowed values.  One place to define them; the CHECK constraints below are
#  built from these so Python and the database can never disagree.
# ============================================================================

class ProcessingStatus(str, enum.Enum):
    """Life of an uploaded file. Only COMPLETED rows have a candidate_id."""
    UPLOADED = "UPLOADED"        # saved, waiting in the queue
    PROCESSING = "PROCESSING"    # the AI is reading it now
    EXTRACTED = "EXTRACTED"      # AI finished, still being linked to a person
    COMPLETED = "COMPLETED"      # done - profile is ready
    FAILED = "FAILED"            # broken file, see failure_reason
    REJECTED = "REJECTED"        # duplicate file, nothing created


class FileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"


class DuplicateType(str, enum.Enum):
    EXACT_FILE_MATCH = "EXACT_FILE_MATCH"   # same bytes (file hash) - certain
    EMAIL_MATCH = "EMAIL_MATCH"             # strong identity signal
    PHONE_MATCH = "PHONE_MATCH"             # strong identity signal
    SEMANTIC_MATCH = "SEMANTIC_MATCH"       # vector similarity - never auto-merged


class DuplicateAction(str, enum.Enum):
    NEW_CANDIDATE_CREATED = "NEW_CANDIDATE_CREATED"
    RESUME_APPENDED = "RESUME_APPENDED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"   # reserved, not produced yet


class CandidateStatus(str, enum.Enum):
    """HR pipeline status, shared across Modules 2/3/6.
    See docs/api-contracts/resume_ingestion.md open question 1 and
    migrations/versions/5463c2581d0d_add_candidate_pipeline_status.py."""
    FILTERED = "FILTERED"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    INACTIVE = "INACTIVE"
    ROUND1_SCORED = "ROUND1_SCORED"
    SHORTLISTED = "SHORTLISTED"
    ROUND2_SCORED = "ROUND2_SCORED"
    FINAL_DECISION = "FINAL_DECISION"


def _sql_list(values: type[enum.Enum]) -> str:
    """ProcessingStatus -> "'UPLOADED','PROCESSING',..."  for use inside CHECK (... IN (...))."""
    return ", ".join(f"'{member.value}'" for member in values)


# ============================================================================
#  1. candidates - the PERSON
# ============================================================================

class Candidate(Base):
    __tablename__ = "candidates"

    # ---- identity -------------------------------------------------------
    #  BigInteger + primary_key + autoincrement  ==>  BIGSERIAL in Postgres.
    candidate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ---- contact --------------------------------------------------------
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))       # AI may not find one
    phone: Mapped[str | None] = mapped_column(String(30))        # last 10 digits only

    # ---- current position -----------------------------------------------
    current_location: Mapped[str | None] = mapped_column(String(255))
    current_job_title: Mapped[str | None] = mapped_column(String(255))
    current_company: Mapped[str | None] = mapped_column(String(255))
    experience_years: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))   # 8.50 is valid

    # ---- profile content (JSON arrays, never null) ----------------------
    skills: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    education: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    experience: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    certifications: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))

    # ---- AI traceability ------------------------------------------------
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))   # 0.00 - 1.00
    raw_profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)         # untouched LLM output

    # ---- record lifecycle -----------------------------------------------
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=CandidateStatus.FILTERED.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # updated_at is refreshed by the trigger trg_candidates_updated_at (created in the migration).

    # ---- links to other tables ------------------------------------------
    resumes: Mapped[list["Resume"]] = relationship(back_populates="candidate", passive_deletes=True)
    embeddings: Mapped[list["CandidateEmbedding"]] = relationship(back_populates="candidate", passive_deletes=True)

    @property
    def resume_count(self) -> int:
        """Number of resume files stored for this person. Read by GET /candidates/{id}."""
        return len(self.resumes)

    # ---- guard rails + indexes (mirror candidates.sql exactly) ----------
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_candidates_name_not_blank"),
        CheckConstraint("experience_years IS NULL OR experience_years BETWEEN 0 AND 70",
                        name="ck_candidates_experience_range"),
        CheckConstraint("extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1",
                        name="ck_candidates_confidence_range"),
        CheckConstraint("email IS NULL OR email = lower(email)", name="ck_candidates_email_lowercase"),
        CheckConstraint("phone IS NULL OR phone ~ '^[0-9]{10}$'", name="ck_candidates_phone_digits"),
        CheckConstraint("jsonb_typeof(skills) = 'array'", name="ck_candidates_skills_is_array"),
        CheckConstraint("jsonb_typeof(education) = 'array'", name="ck_candidates_education_is_array"),
        CheckConstraint("jsonb_typeof(experience) = 'array'", name="ck_candidates_experience_is_array"),
        CheckConstraint("jsonb_typeof(certifications) = 'array'", name="ck_candidates_certifications_is_array"),
        CheckConstraint(f"status IN ({_sql_list(CandidateStatus)})", name="ck_candidates_status"),

        Index("ix_candidates_phone", "phone", postgresql_where=text("phone IS NOT NULL")),
        Index("ix_candidates_status", "status"),
        Index("ix_candidates_job_title", "current_job_title"),
        Index("ix_candidates_experience", "experience_years"),
        Index("ix_candidates_location", "current_location"),
        Index("ix_candidates_skills_gin", "skills", postgresql_using="gin"),
        Index("ix_candidates_certifications_gin", "certifications", postgresql_using="gin"),
        Index("ix_candidates_active", text("created_at DESC"), postgresql_where=text("is_active")),
        {"comment": "Master candidate profile. One row per human being. Owned by Module 1."},
    )


#  UNIQUE on lower(email): two candidates can never share an email.
#  Defined outside the class because it uses a function on the column.
Index(
    "ux_candidates_email",
    func.lower(Candidate.email),
    unique=True,
    postgresql_where=Candidate.email.isnot(None),
)


# ============================================================================
#  2. resumes - the FILES
# ============================================================================

class Resume(Base):
    __tablename__ = "resumes"

    resume_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ---- link to the person ---------------------------------------------
    #  NULL until the LLM extraction identifies the candidate.
    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.candidate_id", ondelete="CASCADE")
    )
    resume_version: Mapped[int | None] = mapped_column(Integer)   # 1, 2, 3 ... set with candidate_id

    # ---- the file itself ------------------------------------------------
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)    # original name from HR
    file_path: Mapped[str] = mapped_column(Text, nullable=False)           # path on local disk
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)     # pdf / docx / doc / txt
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)     # SHA-256 hex

    # ---- processing pipeline --------------------------------------------
    processing_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=ProcessingStatus.UPLOADED.value
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)     # required when FAILED
    extracted_text: Mapped[str | None] = mapped_column(Text)     # words pulled from the file

    # ---- version control ------------------------------------------------
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # ---- timestamps -----------------------------------------------------
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # ---- links ----------------------------------------------------------
    candidate: Mapped["Candidate | None"] = relationship(back_populates="resumes")
    embeddings: Mapped[list["CandidateEmbedding"]] = relationship(back_populates="resume", passive_deletes=True)

    __table_args__ = (
        CheckConstraint(f"processing_status IN ({_sql_list(ProcessingStatus)})", name="ck_resumes_status"),
        CheckConstraint(f"file_type IN ({_sql_list(FileType)})", name="ck_resumes_file_type"),
        CheckConstraint("file_hash ~ '^[0-9a-f]{64}$'", name="ck_resumes_hash_format"),
        CheckConstraint("file_size_bytes > 0 AND file_size_bytes <= 10485760", name="ck_resumes_size_positive"),
        CheckConstraint("processing_status <> 'FAILED' OR failure_reason IS NOT NULL",
                        name="ck_resumes_failed_has_reason"),
        CheckConstraint(
            "(candidate_id IS NULL AND resume_version IS NULL) "
            "OR (candidate_id IS NOT NULL AND resume_version IS NOT NULL)",
            name="ck_resumes_version_with_candidate",
        ),
        CheckConstraint("is_latest = false OR candidate_id IS NOT NULL", name="ck_resumes_latest_needs_candidate"),
        CheckConstraint("resume_version IS NULL OR resume_version >= 1", name="ck_resumes_version_positive"),

        #  The identical file can never be stored twice (EXACT_FILE_MATCH, enforced by the DB).
        Index("ux_resumes_file_hash", "file_hash", unique=True),
        #  One candidate cannot have two "version 2" resumes.
        Index("ux_resumes_version", "candidate_id", "resume_version", unique=True,
              postgresql_where=text("candidate_id IS NOT NULL")),
        #  One candidate has exactly ONE latest resume.
        Index("ux_resumes_one_latest", "candidate_id", unique=True,
              postgresql_where=text("is_latest = true")),
        Index("ix_resumes_candidate", "candidate_id", text("resume_version DESC")),
        Index("ix_resumes_status", "processing_status"),
        Index("ix_resumes_pending", "created_at",
              postgresql_where=text("processing_status IN ('UPLOADED','PROCESSING')")),
        {"comment": "One row per uploaded resume file. Exactly one per candidate carries is_latest = TRUE. Owned by Module 1."},
    )


# ============================================================================
#  3. candidate_embeddings - the MEANING
# ============================================================================

EMBEDDING_DIMENSIONS = 768   # nomic-embed-text always outputs exactly 768 numbers


class CandidateEmbedding(Base):
    """ONE row per candidate (the active one): JSONB profile + its text + its vector.

    profile_metadata (JSONB) = the information Module 2 gives the LLM.
    embedding        (vector) = what search ranks with.  See candidate_embeddings.sql.
    """
    __tablename__ = "candidate_embeddings"

    embedding_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ---- links (both required: a vector exists only after the person + file do)
    candidate_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("resumes.resume_id", ondelete="CASCADE"), nullable=False
    )

    # ---- the profile, its text, its vector ------------------------------
    #  NOT named "metadata" - that attribute name is reserved by SQLAlchemy.
    profile_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)   # snapshot of the person
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)                 # the exact words embedded - never drop
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

    # ---- AI traceability ------------------------------------------------
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of embedding_text

    # ---- lifecycle ------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # ---- links ----------------------------------------------------------
    candidate: Mapped["Candidate"] = relationship(back_populates="embeddings")
    resume: Mapped["Resume"] = relationship(back_populates="embeddings")

    __table_args__ = (
        CheckConstraint("length(trim(embedding_text)) > 0", name="ck_emb_text_not_blank"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_emb_content_hash_format"),
        CheckConstraint("length(trim(model_name)) > 0", name="ck_emb_model_name_not_blank"),
        CheckConstraint("jsonb_typeof(profile_metadata) = 'object'", name="ck_emb_metadata_is_object"),

        #  One resume version produces at most one vector.
        Index("ux_emb_resume", "resume_id", unique=True),
        #  Exactly one LIVE vector per candidate (also serves the lookup).
        Index("ux_emb_candidate_active", "candidate_id", unique=True, postgresql_where=text("is_active")),
        #  THE SEARCH INDEX - HNSW, cosine distance, active rows only.
        Index(
            "ix_emb_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("is_active"),
        ),
        {"comment": "One semantic vector per candidate plus the JSONB profile it was built from. Owned by Module 1, queried by Module 2."},
    )


# ============================================================================
#  4. duplicate_tracking - the DIARY (append-only, no updated_at, no trigger)
# ============================================================================

class DuplicateTracking(Base):
    __tablename__ = "duplicate_tracking"

    duplicate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # ---- the INCOMING record that triggered this event -------------------
    #  resume_id is NULL when the file was rejected before a resumes row existed.
    resume_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("resumes.resume_id", ondelete="CASCADE")
    )
    candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.candidate_id", ondelete="SET NULL")
    )

    # ---- the EXISTING record we matched against --------------------------
    #  SET NULL, not CASCADE: the diary entry outlives the record it points at.
    matched_candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidates.candidate_id", ondelete="SET NULL")
    )
    matched_resume_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("resumes.resume_id", ondelete="SET NULL")
    )
    matched_embedding_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("candidate_embeddings.embedding_id", ondelete="SET NULL")
    )

    # ---- the verdict ----------------------------------------------------
    duplicate_type: Mapped[str] = mapped_column(String(50), nullable=False)      # HOW it was detected
    duplicate_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))   # 0.00 - 1.00
    action_taken: Mapped[str] = mapped_column(String(100), nullable=False)       # WHAT the system did

    # ---- the evidence and the undo button -------------------------------
    detection_details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    old_raw_profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)   # profile BEFORE
    new_raw_profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)   # profile AFTER

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    #  No relationship() attributes here on purpose: this table points at
    #  candidates twice and resumes twice, so SQLAlchemy cannot guess which
    #  foreign key a relationship means. Add them with foreign_keys=[...]
    #  when a phase actually needs to navigate from a diary row.

    __table_args__ = (
        CheckConstraint(f"duplicate_type IN ({_sql_list(DuplicateType)})", name="ck_dup_type"),
        CheckConstraint(f"action_taken IN ({_sql_list(DuplicateAction)})", name="ck_dup_action"),
        CheckConstraint("duplicate_confidence IS NULL OR duplicate_confidence BETWEEN 0 AND 1",
                        name="ck_dup_confidence_range"),
        CheckConstraint("duplicate_type <> 'SEMANTIC_MATCH' OR duplicate_confidence IS NOT NULL",
                        name="ck_dup_semantic_needs_confidence"),
        CheckConstraint(
            "matched_candidate_id IS NOT NULL OR matched_resume_id IS NOT NULL OR matched_embedding_id IS NOT NULL",
            name="ck_dup_matched_something",
        ),
        CheckConstraint("jsonb_typeof(detection_details) = 'object'", name="ck_dup_details_is_object"),

        Index("ix_dup_candidate", "candidate_id", postgresql_where=text("candidate_id IS NOT NULL")),
        Index("ix_dup_matched_candidate", "matched_candidate_id",
              postgresql_where=text("matched_candidate_id IS NOT NULL")),
        Index("ix_dup_resume", "resume_id"),
        Index("ix_dup_review_queue", "created_at",
              postgresql_where=text("action_taken = 'MANUAL_REVIEW_REQUIRED'")),
        Index("ix_dup_type", "duplicate_type"),
        Index("ix_dup_created", text("created_at DESC")),
        {"comment": "Append-only audit log of duplicate detection events. Evidence only - drives no behaviour. Owned by Module 1."},
    )
