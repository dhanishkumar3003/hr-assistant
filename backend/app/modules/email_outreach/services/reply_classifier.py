"""
Reply classification logic.

Classifies candidate replies as interested, declined, or needing review.
Rule-based phrase matching handles the common ways candidates actually
reply to interview invitations; anything ambiguous falls through to the
Ollama-hosted LLM classifier (llm_reply_classifier.py) before finally
defaulting to manual review.

The pattern lists below were centralized in this project's config
module originally; kept local here instead, since this codebase's
Settings (pydantic-settings, env-var-backed) isn't a natural home for
Python regex lists the way a plain config.py was.
"""

import re
import logging
from app.modules.email_outreach.services.email_parser import strip_quoted_content

log = logging.getLogger(__name__)

# Classification result constants
CLASSIFICATION_INTERESTED = "interested"
CLASSIFICATION_DECLINED = "declined"
CLASSIFICATION_NEEDS_REVIEW = "needs_review"

# How a classification was produced - stored alongside the result
# (see CandidateResponse.classification_source) so it's visible later
# which replies were caught by the cheap regex pass vs needed the LLM.
SOURCE_REGEX = "reply_email_regex"
SOURCE_LLM = "reply_email_llm"

# Maps llm_reply_classifier's labels onto the constants above
_LLM_LABEL_TO_CLASSIFICATION = {
    "INTERESTED": CLASSIFICATION_INTERESTED,
    "NOT_INTERESTED": CLASSIFICATION_DECLINED,
    "OTHER": CLASSIFICATION_NEEDS_REVIEW,
}

# Auto-replies aren't a real response from the candidate - route straight
# to review instead of risking a false interested/declined match on
# whatever boilerplate the OOO message happens to contain.
REPLY_AUTO_REPLY_PATTERNS = [
    r"\bout of office\b",
    r"\bautomatic reply\b",
    r"\bauto-reply\b",
    r"\bi\s*am\s*currently\s*out\b",
    r"\bon\s*(vacation|leave|pto)\b",
    r"\bcurrently unavailable\b",
]

# Checked before interest patterns so mixed replies ("interested, but I
# have to pass") land on decline rather than a false positive.
REPLY_DECLINED_PATTERNS = [
    r"\bnot interested\b",
    r"\bno longer interested\b",
    r"\bnot a good fit\b",
    r"\bpursuing other opportunities\b",
    r"\baccepted (another|a different) (offer|position|role)\b",
    r"\bwithdraw(ing)?\s*my\s*application\b",
    r"\bplease remove me\b",
    r"\bunsubscribe\b",
    r"\bno thanks?\b",
    r"\bnot\s*(moving forward|the right time|right now)\b",
    r"\bi(?:'|’)?ll(?:\s+\w+){0,3}\s+pass\b",
    r"\bdecline\b",
    r"\bnot\s*a\s*match\b",
]

REPLY_INTERESTED_PATTERNS = [
    r"\byes\b",
    r"\bi(?:'|’)?m\s*interested\b",
    r"\bi\s*am\s*interested\b",
    r"\bsounds good\b",
    r"\bcount me in\b",
    r"\b(i(?:'|’)?d|i would) love to\b",
    r"\bhappy to\b",
    r"\blet(?:'|’)?s schedule\b",
    r"\b(i(?:'|’)?m|i am)\s*available\b",
    r"\bworks for me\b",
    r"\blooking forward\b",
    r"\bplease send\b",
    r"\bi confirm\b",
    r"\bi accept\b",
    r"\bwhen can we\b",
    r"\bwhat time works\b",
    r"\binterested\b",
]


def classify_reply(body: str) -> str:
    """
    Classify a candidate reply based on email body content.

    Args:
        body (str): Email body text.

    Returns:
        str: Classification: 'interested', 'declined', or 'needs_review'.
    """
    classification, _source = classify_reply_with_source(body)
    return classification


def classify_reply_with_source(body: str) -> tuple:
    """
    Classify a candidate reply and report which method produced it.

    Phrase-based matching handles common interview-reply patterns first;
    anything that doesn't match is sent to the LLM classifier before
    falling back to needs_review. Quoted/forwarded content (the
    original invitation email most clients paste below a reply) is cut
    off first - it can otherwise contain phrases like "Decline
    Invitation" from our own email's buttons, which would misclassify
    a reply that never said any such thing.

    Args:
        body (str): Email body text.

    Returns:
        tuple: (classification, source) - source is SOURCE_REGEX or
            SOURCE_LLM.
    """
    new_content = strip_quoted_content(body) or (body or "")
    text = new_content.lower()

    if _matches_any(text, REPLY_AUTO_REPLY_PATTERNS):
        return CLASSIFICATION_NEEDS_REVIEW, SOURCE_REGEX

    if _matches_any(text, REPLY_DECLINED_PATTERNS):
        return CLASSIFICATION_DECLINED, SOURCE_REGEX

    if _matches_any(text, REPLY_INTERESTED_PATTERNS):
        return CLASSIFICATION_INTERESTED, SOURCE_REGEX

    # Ambiguous - ask the LLM before giving up to manual review
    return _classify_with_llm(new_content), SOURCE_LLM


def _matches_any(text: str, patterns: list) -> bool:
    """Return True if any regex pattern matches text."""
    return any(re.search(pattern, text) for pattern in patterns)


def _classify_with_llm(body: str) -> str:
    """
    Fall back to the Ollama LLM classifier for ambiguous replies.

    Args:
        body (str): Email body text.

    Returns:
        str: Mapped classification, or needs_review if the LLM is
            unavailable or returns an unrecognized label.
    """
    try:
        from app.modules.email_outreach.services.llm_reply_classifier import classify_reply_llm
        label = classify_reply_llm(body)
    except Exception as exc:
        log.warning(
            f"LLM classification unavailable, defaulting to "
            f"needs_review: {exc}"
        )
        return CLASSIFICATION_NEEDS_REVIEW

    return _LLM_LABEL_TO_CLASSIFICATION.get(label, CLASSIFICATION_NEEDS_REVIEW)
