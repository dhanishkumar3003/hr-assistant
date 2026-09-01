"""
Token management for tracking email replies.

Generates unique tokens/candidate IDs for each candidate invitation and
extracts tokens from email subjects.

Named distinctly from app.shared.interfaces.token_service.ITokenService
(JWT auth tokens) - unrelated concept, same word.
"""

import uuid
import re
import logging

log = logging.getLogger(__name__)


def generate_token() -> str:
    """
    Generate a unique 8-character tracking token.

    Returns:
        str: Unique token string.
    """
    return str(uuid.uuid4())[:8]


def generate_candidate_id() -> str:
    """
    Generate a unique candidate ID (full UUID).

    Public-facing identifier used in the Reply-To plus-tag and the
    draft/status/test-round APIs - unlike generate_token(), this isn't
    truncated, since it doesn't need to fit in a subject line.

    Returns:
        str: UUID string.
    """
    return str(uuid.uuid4())


def extract_token(subject: str) -> str:
    """
    Extract tracking token from email subject.

    Looks for pattern: [Ref:xxxxxxxx]

    Works with replies such as:
        Re: Interview Invitation [Ref:be4c10b9]

    Args:
        subject (str): Email subject line.

    Returns:
        str: Token if found, None otherwise.
    """
    match = re.search(
        r"\[Ref:([a-zA-Z0-9]+)\]",
        subject or ""
    )

    return match.group(1) if match else None
