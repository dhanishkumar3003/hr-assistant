"""
LLM-based reply classification via an OSS model served through Ollama.

Used by reply_classifier.py as a fallback for replies the rule-based
pass can't confidently categorize. Mirrors the intent categories from
the Module 3 PDD: INTERESTED, NOT_INTERESTED, OTHER.
"""

import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings

log = logging.getLogger(__name__)

LLM_INTERESTED = "INTERESTED"
LLM_NOT_INTERESTED = "NOT_INTERESTED"
LLM_OTHER = "OTHER"
VALID_LABELS = {LLM_INTERESTED, LLM_NOT_INTERESTED, LLM_OTHER}

SYSTEM_PROMPT = (
    "You classify a candidate's email reply to a job interview invitation. "
    "Respond with exactly one word: INTERESTED, NOT_INTERESTED, or OTHER.\n\n"
    "INTERESTED - the candidate wants to proceed with the interview process.\n"
    "NOT_INTERESTED - the candidate declines or is withdrawing.\n"
    "OTHER - the reply doesn't clearly fall into either category "
    "(e.g. a question with no stated intent, an auto-reply, or text with "
    "no relation to accepting/declining).\n\n"
    "Replies are often short, casual, and may contain typos or "
    "misspellings (e.g. \"Intrested\", \"yess pls\", \"sure thing\", "
    "\"not intrested rn\") - judge the candidate's clear intent despite "
    "spelling or grammar mistakes; do not classify as OTHER just because "
    "a word is misspelled. Only use OTHER when the intent is genuinely "
    "unclear even after accounting for typos and informal phrasing.\n\n"
    "Examples:\n"
    "Reply: \"Intrested\" -> INTERESTED\n"
    "Reply: \"yes definitely, when can we start\" -> INTERESTED\n"
    "Reply: \"not interested, thanks\" -> NOT_INTERESTED\n"
    "Reply: \"sorry, i've accepted another offer\" -> NOT_INTERESTED\n"
    "Reply: \"what does this role pay?\" -> OTHER\n"
    "Reply: \"I am currently out of office until Monday\" -> OTHER\n\n"
    "Respond with the label only - no punctuation, no explanation."
)

_llm = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0)
    return _llm


def classify_reply_llm(body: str) -> str:
    """
    Classify a candidate reply using the Ollama-hosted LLM.

    Args:
        body (str): Candidate reply text.

    Returns:
        str: One of LLM_INTERESTED, LLM_NOT_INTERESTED, LLM_OTHER.

    Raises:
        RuntimeError: If the Ollama call fails (server down, model
            missing, network error, etc).
    """
    text = (body or "").strip()
    if not text:
        return LLM_OTHER

    try:
        response = _get_llm().invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=text[:4000]),
            ]
        )
    except Exception as exc:
        raise RuntimeError(f"Ollama classification failed: {exc}") from exc

    label = (response.content or "").strip().upper()

    for valid in VALID_LABELS:
        if valid in label:
            return valid

    log.warning(f"LLM returned unrecognized label '{label}' - treating as OTHER.")
    return LLM_OTHER
