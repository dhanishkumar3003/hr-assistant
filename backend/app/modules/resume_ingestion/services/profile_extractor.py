"""
Module 1 - turning resume TEXT into a structured PROFILE with the LLM.

    IProfileExtractor  -> LLMProfileExtractor  (real, via get_llm_service())
                       -> anything that fakes it in tests

The LLM is asked for strict JSON. The answer is validated and cleaned by
ExtractedProfile (Pydantic) so that whatever reaches the database already
satisfies its CHECK constraints. One retry on bad JSON, then give up with a
clear reason.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.modules.resume_ingestion.prompts.extraction_prompt import SYSTEM_PROMPT, build_user_prompt
from app.shared.interfaces.llm_service import ILLMService

MAX_RESUME_CHARS = 12_000   # roughly 3,000 tokens - protects the model's context window
MAX_ATTEMPTS = 2            # first try + one retry


class ProfileExtractionError(Exception):
    """The LLM could not produce a usable profile. The message becomes resumes.failure_reason."""


# ---------------------------------------------------------------------------
#  Small cleaners used by the validators below
# ---------------------------------------------------------------------------
def _clean_str(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]                      # a single string / object -> one-item list


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value))   # "8.5 years" -> 8.5
    return float(match.group()) if match else None


# ---------------------------------------------------------------------------
#  What a validated profile looks like
# ---------------------------------------------------------------------------
class ExtractedProfile(BaseModel):
    """The 13 known fields, cleaned. Extra keys the LLM adds are kept (extra='allow')."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    current_location: str | None = None
    current_job_title: str | None = None
    current_company: str | None = None
    experience_years: float | None = None
    skills: list[str] = []
    education: list[dict[str, Any]] = []
    experience: list[dict[str, Any]] = []
    certifications: list[str] = []
    linkedin_url: str | None = None
    extraction_confidence: float | None = None

    @field_validator("name", "email", "phone", "current_location", "current_job_title",
                     "current_company", "linkedin_url", mode="before")
    @classmethod
    def _strings(cls, value: Any) -> str | None:
        return _clean_str(value)

    @field_validator("skills", "certifications", mode="before")
    @classmethod
    def _string_lists(cls, value: Any) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in _as_list(value):
            if isinstance(item, dict):                      # {"name": "Java"} -> "Java"
                item = item.get("name") or item.get("skill") or item.get("title")
            text = _clean_str(item)
            if text and text.lower() not in seen:            # dedupe, case-insensitive
                seen.add(text.lower())
                cleaned.append(text)
        return cleaned

    @field_validator("education", "experience", mode="before")
    @classmethod
    def _object_lists(cls, value: Any) -> list[dict[str, Any]]:
        return [
            item if isinstance(item, dict) else {"text": str(item).strip()}
            for item in _as_list(value)
            if item not in (None, "")
        ]

    @field_validator("experience_years", mode="before")
    @classmethod
    def _years(cls, value: Any) -> float | None:
        number = _to_number(value)
        return number if number is not None and 0 <= number <= 70 else None    # ck_candidates_experience_range

    @field_validator("extraction_confidence", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> float | None:
        number = _to_number(value)
        if number is None:
            return None
        if 1 < number <= 100:                                  # model answered in percent
            number = number / 100
        return number if 0 <= number <= 1 else None            # ck_candidates_confidence_range


# ---------------------------------------------------------------------------
#  The interface and the real implementation
# ---------------------------------------------------------------------------
class IProfileExtractor(ABC):
    @abstractmethod
    def extract(self, resume_text: str) -> tuple[ExtractedProfile, dict[str, Any]]:
        """Return (validated profile, the raw LLM dict). Raise ProfileExtractionError when hopeless."""


class LLMProfileExtractor(IProfileExtractor):
    def __init__(self, llm: ILLMService, max_chars: int = MAX_RESUME_CHARS, attempts: int = MAX_ATTEMPTS):
        self._llm = llm
        self._max_chars = max_chars
        self._attempts = attempts

    def extract(self, resume_text: str) -> tuple[ExtractedProfile, dict[str, Any]]:
        user_prompt = build_user_prompt(resume_text[: self._max_chars])
        last_error: Exception | None = None

        for _ in range(self._attempts):
            try:
                raw = self._llm.complete_json(SYSTEM_PROMPT, user_prompt)
            except (json.JSONDecodeError, ValueError) as exc:     # model ignored "JSON only" - try again
                last_error = exc
                continue
            except Exception as exc:                                # Ollama down, timeout, network ...
                raise ProfileExtractionError(f"LLM call failed: {type(exc).__name__}: {exc}") from exc

            if not isinstance(raw, dict):
                last_error = ValueError("LLM returned JSON that is not an object")
                continue

            try:
                return ExtractedProfile.model_validate(raw), raw
            except ValidationError as exc:
                last_error = exc
                continue

        raise ProfileExtractionError(
            f"LLM did not return a usable profile after {self._attempts} attempts: {last_error}"
        )
