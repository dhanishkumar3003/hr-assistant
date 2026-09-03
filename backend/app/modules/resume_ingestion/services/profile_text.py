"""
Module 1 - the candidate profile as ONE JSON object and ONE compact text.

    candidate row --build_profile_metadata()--> dict  (stored as JSONB: the source of truth)
    dict          --render_profile_text()-----> str   (stored as embedding_text: what the model reads)

One candidate = one JSON = one text = one vector (see candidate_embeddings.sql).
Replaced the SectionChunker (2-5 chunks per resume) on 2026-08-26.

RULES
  * Everything flexible about the person goes in the dict (skills, education,
    experience, company, phone ...). A new attribute is a new KEY, never a new
    database column.
  * The text leaves OUT email / phone / LinkedIn: they are identity, not
    meaning, and only add noise to the vector. They stay in the JSON.
  * The text must be deterministic: same dict -> same text -> same SHA-256.
    That is what lets the embedder skip a profile that has not changed.
"""

from typing import Any

#  The keys every profile_metadata object carries, in this order.
PROFILE_METADATA_KEYS: tuple[str, ...] = (
    "name", "email", "phone",
    "current_location", "current_job_title", "current_company", "experience_years",
    "skills", "education", "experience", "certifications", "linkedin_url",
    "summary",
)


def build_profile_metadata(candidate: Any) -> dict[str, Any]:
    """The candidates row (ORM object or test double) -> the JSONB object.

    Reads the 12 known profile columns plus `summary` out of raw_profile_json
    (the LLM's summary has no column of its own but is gold for search).
    experience_years is forced to float: Postgres hands back Decimal, and JSON
    has no Decimal.
    """
    raw = getattr(candidate, "raw_profile_json", None)
    years = getattr(candidate, "experience_years", None)
    return {
        "name": _clean(getattr(candidate, "name", None)),
        "email": _clean(getattr(candidate, "email", None)),
        "phone": _clean(getattr(candidate, "phone", None)),
        "current_location": _clean(getattr(candidate, "current_location", None)),
        "current_job_title": _clean(getattr(candidate, "current_job_title", None)),
        "current_company": _clean(getattr(candidate, "current_company", None)),
        "experience_years": float(years) if years is not None else None,
        "skills": _as_list(getattr(candidate, "skills", None)),
        "education": _as_list(getattr(candidate, "education", None)),
        "experience": _as_list(getattr(candidate, "experience", None)),
        "certifications": _as_list(getattr(candidate, "certifications", None)),
        "linkedin_url": _clean(getattr(candidate, "linkedin_url", None)),
        "summary": _clean(raw.get("summary")) if isinstance(raw, dict) else None,
    }


def render_profile_text(metadata: dict[str, Any]) -> str:
    """The JSON -> compact lines for the embedding model. Deterministic.

        Ravi Kumar | Lead Software Engineer | Infosys | Chennai, Tamil Nadu | 9.5 years experience
        Summary: Backend engineer with 9+ years ...
        Skills: Java, Spring Boot, Kafka, ...
        Experience: Lead Software Engineer at Infosys (2025-01 to present); ...
        Education: B.E. Computer Science and Engineering, Anna University, 2017
        Certifications: AWS Certified Developer - Associate (2022)

    Lines with nothing to say are left out. Returns '' for an empty profile -
    the embedder then falls back to the raw resume text.
    """
    years = metadata.get("experience_years")
    header = " | ".join(filter(None, [
        _clean(metadata.get("name")),
        _clean(metadata.get("current_job_title")),
        _clean(metadata.get("current_company")),
        _clean(metadata.get("current_location")),
        f"{float(years):g} years experience" if years is not None else None,
    ]))
    lines = [
        header,
        _line("Summary", _clean(metadata.get("summary"))),
        _line("Skills", ", ".join(_strings(metadata.get("skills")))),
        _line("Experience", "; ".join(filter(None, (_render_job(j) for j in _as_list(metadata.get("experience")))))),
        _line("Education", "; ".join(filter(None, (_render_education(e) for e in _as_list(metadata.get("education")))))),
        _line("Certifications", "; ".join(_strings(metadata.get("certifications")))),
    ]
    return "\n".join(filter(None, lines)).strip()


# ---------------------------------------------------------------------------
#  helpers
# ---------------------------------------------------------------------------
def _render_job(job: Any) -> str:
    """{"role","company","from","to"} -> 'Role at Company (from to to)'. A plain string is used as-is."""
    if not isinstance(job, dict):
        return _clean(job) or ""
    role = _clean(job.get("role")) or _clean(job.get("title"))
    company = _clean(job.get("company"))
    span = " to ".join(filter(None, [_clean(job.get("from")), _clean(job.get("to"))]))
    text = _clean(job.get("text")) or " at ".join(filter(None, [role, company]))
    return " ".join(filter(None, [text, f"({span})" if span else None]))


def _render_education(edu: Any) -> str:
    """{"degree","institution","year"} -> 'Degree, Institution, Year'. A plain string is used as-is."""
    if not isinstance(edu, dict):
        return _clean(edu) or ""
    return _clean(edu.get("text")) or ", ".join(filter(None, [
        _clean(edu.get("degree")), _clean(edu.get("institution")), _clean(edu.get("year")),
    ]))


def _line(label: str, value: str | None) -> str | None:
    return f"{label}: {value}" if value else None


def _strings(values: Any) -> list[str]:
    return [s for s in (_clean(v) for v in _as_list(values)) if s]


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
