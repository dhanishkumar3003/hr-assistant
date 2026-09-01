"""
LLM-generated rejection draft copy.

Generates the free-text portions of a candidate_rejection.html draft
(the parts that read as genuinely personalized rather than boilerplate)
via the same Ollama-hosted LLM llm_reply_classifier.py uses, given the
candidate/job context. Kept separate from services/drafter.py (which
only knows how to fill a template and hold a draft) and
confirmation_content.py (static copy, not LLM-generated) - this is the
one place that talks to the LLM for rejection wording specifically.
"""

import logging

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You write the body paragraph of a candidate rejection email for a "
    "recruitment team. Write 2-3 short sentences: thank the candidate for "
    "applying, state that the company will not be moving forward with their "
    "application for this specific role, and keep the tone warm, respectful, "
    "and free of specific reasons for rejection (never mention other "
    "candidates being 'better' or cite any specific weakness). "
    "Respond with only the paragraph text - no greeting, no signature, no "
    "subject line, no markdown."
)

_llm = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0.4)
    return _llm


def generate_rejection_paragraph(candidate_name: str, job_role: str, company_name: str) -> str:
    """
    Generate the personalized rejection paragraph for a candidate.

    Args:
        candidate_name (str): Candidate's name.
        job_role (str): Role they applied for.
        company_name (str): Hiring company's name.

    Returns:
        str: A short rejection paragraph. Falls back to a static
            default if the LLM call fails, so drafting never blocks on
            Ollama being unavailable.
    """
    prompt = (
        f"Candidate name: {candidate_name or 'the candidate'}\n"
        f"Role applied for: {job_role or 'the position'}\n"
        f"Company: {company_name or settings.company_name}"
    )

    try:
        response = _get_llm().invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        text = (response.content or "").strip()
        if text:
            return text
    except Exception as exc:
        log.warning(f"LLM rejection paragraph generation failed, using default: {exc}")

    return (
        f"We appreciate the time and effort you invested in the recruitment "
        f"process. After careful consideration of your application, we have "
        f"decided not to move forward with your application for this "
        f"position at this time."
    )
