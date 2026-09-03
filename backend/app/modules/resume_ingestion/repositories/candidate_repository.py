"""
Module 1 - the ONLY class allowed to read or write the `candidates` table.

NOTE  shared/interfaces/candidate_repository.py - the interface OTHER modules
will call - is still commented out in git, pending the UUID-vs-integer
decision. Until that is settled this module-local interface is the contract;
CandidateRepository will implement the shared one as well once it exists.
"""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.resume_ingestion.models import Candidate


class CandidateWriteError(Exception):
    """The database refused the row (a CHECK or UNIQUE rule). The message names the rule."""


class CandidateAlreadyExistsError(CandidateWriteError):
    """ux_candidates_email: another candidate already has this email address."""


class ICandidateRepository(ABC):
    @abstractmethod
    def get_by_id(self, candidate_id: int) -> Candidate | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Candidate | None:
        """Case-insensitive. Includes inactive candidates - the unique index does too."""

    @abstractmethod
    def get_by_phone(self, phone: str) -> Candidate | None:
        """Exact match on the normalised 10 digits. Phone is NOT unique (families share
        numbers); when several candidates share it, the most recently created wins."""

    @abstractmethod
    def create(
        self, *,
        name: str,
        email: str | None,
        phone: str | None,
        current_location: str | None,
        current_job_title: str | None,
        current_company: str | None,
        experience_years: float | None,
        skills: list[str],
        education: list[dict[str, Any]],
        experience: list[dict[str, Any]],
        certifications: list[str],
        linkedin_url: str | None,
        extraction_confidence: float | None,
        raw_profile_json: dict[str, Any],
    ) -> Candidate:
        """Insert one person. email/phone must already be normalised. Raises CandidateWriteError."""

    @abstractmethod
    def update_profile(
        self, candidate_id: int, *,
        name: str,
        email: str | None,
        phone: str | None,
        current_location: str | None,
        current_job_title: str | None,
        current_company: str | None,
        experience_years: float | None,
        skills: list[str],
        education: list[dict[str, Any]],
        experience: list[dict[str, Any]],
        certifications: list[str],
        linkedin_url: str | None,
        extraction_confidence: float | None,
        raw_profile_json: dict[str, Any],
    ) -> Candidate:
        """Overwrite the 14 profile columns of an existing person. Raises CandidateWriteError."""


class CandidateRepository(ICandidateRepository):
    def __init__(self, db: Session):
        self._db = db

    # ---- reads ----------------------------------------------------------
    def get_by_id(self, candidate_id: int) -> Candidate | None:
        return self._db.get(Candidate, candidate_id)

    def get_by_email(self, email: str) -> Candidate | None:
        return self._db.execute(
            select(Candidate).where(func.lower(Candidate.email) == email.strip().lower())
        ).scalar_one_or_none()

    def get_by_phone(self, phone: str) -> Candidate | None:
        return self._db.execute(
            select(Candidate)
            .where(Candidate.phone == phone)
            .order_by(Candidate.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    # ---- writes ---------------------------------------------------------
    def create(
        self, *,
        name: str,
        email: str | None,
        phone: str | None,
        current_location: str | None,
        current_job_title: str | None,
        current_company: str | None,
        experience_years: float | None,
        skills: list[str],
        education: list[dict[str, Any]],
        experience: list[dict[str, Any]],
        certifications: list[str],
        linkedin_url: str | None,
        extraction_confidence: float | None,
        raw_profile_json: dict[str, Any],
    ) -> Candidate:
        # Same 14 parameters as the interface, on purpose (Liskov): a caller written
        # against ICandidateRepository can never pass something this class rejects.
        candidate = Candidate(
            name=name,
            email=email,
            phone=phone,
            current_location=current_location,
            current_job_title=current_job_title,
            current_company=current_company,
            experience_years=experience_years,
            skills=skills,
            education=education,
            experience=experience,
            certifications=certifications,
            linkedin_url=linkedin_url,
            extraction_confidence=extraction_confidence,
            raw_profile_json=raw_profile_json,
        )
        self._db.add(candidate)
        self._commit_or_explain()
        self._db.refresh(candidate)
        return candidate

    def update_profile(
        self, candidate_id: int, *,
        name: str,
        email: str | None,
        phone: str | None,
        current_location: str | None,
        current_job_title: str | None,
        current_company: str | None,
        experience_years: float | None,
        skills: list[str],
        education: list[dict[str, Any]],
        experience: list[dict[str, Any]],
        certifications: list[str],
        linkedin_url: str | None,
        extraction_confidence: float | None,
        raw_profile_json: dict[str, Any],
    ) -> Candidate:
        candidate = self._db.get(Candidate, candidate_id)
        if candidate is None:
            raise CandidateWriteError(f"candidate {candidate_id} not found")
        candidate.name = name
        candidate.email = email
        candidate.phone = phone
        candidate.current_location = current_location
        candidate.current_job_title = current_job_title
        candidate.current_company = current_company
        candidate.experience_years = experience_years
        candidate.skills = skills
        candidate.education = education
        candidate.experience = experience
        candidate.certifications = certifications
        candidate.linkedin_url = linkedin_url
        candidate.extraction_confidence = extraction_confidence
        candidate.raw_profile_json = raw_profile_json
        self._commit_or_explain()
        self._db.refresh(candidate)
        return candidate

    def _commit_or_explain(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()                     # leave the session usable for mark_failed()
            reason = str(exc.orig).strip().splitlines()[0]
            if "ux_candidates_email" in reason:
                raise CandidateAlreadyExistsError(reason) from exc
            raise CandidateWriteError(reason) from exc
