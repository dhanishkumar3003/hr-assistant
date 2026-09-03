"""
Module 1 - combining what we already know about a person with a newer resume.

Rule: the NEWER resume wins, column by column - but a blank in the new resume
never erases a value we already had. (Ravi's new CV forgot his LinkedIn URL;
that does not mean he deleted his account.)

raw_profile_json is replaced whole: it is the newest LLM output. The old one
is saved in duplicate_tracking.old_raw_profile_json first - the undo button.
"""

from decimal import Decimal
from typing import Any

PROFILE_COLUMNS: tuple[str, ...] = (
    "name", "email", "phone",
    "current_location", "current_job_title", "current_company", "experience_years",
    "skills", "education", "experience", "certifications", "linkedin_url",
    "extraction_confidence", "raw_profile_json",
)


def snapshot(candidate: Any) -> dict[str, Any]:
    """The 14 profile columns of a candidate row, as a plain dict."""
    return {column: getattr(candidate, column) for column in PROFILE_COLUMNS}


def merge_profile(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for column in PROFILE_COLUMNS:
        new_value = incoming.get(column)
        merged[column] = new_value if _present(new_value) else current.get(column)
    return merged


def profile_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """True if any column other than raw_profile_json actually changed."""
    return any(
        _comparable(before.get(column)) != _comparable(after.get(column))
        for column in PROFILE_COLUMNS
        if column != "raw_profile_json"
    )


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _comparable(value: Any) -> Any:
    # The database hands back Decimal('8.50'); the LLM hands back 8.5. Same thing.
    return float(value) if isinstance(value, Decimal) else value
