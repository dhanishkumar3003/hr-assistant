"""
Resolves a raw email to the candidate token it's replying about.

Tries three independent signals, most to least reliable:
1. Message-ID threading (In-Reply-To/References) - the RFC 5322
   mechanism every mail client sets automatically on a genuine reply.
   Also inherently proves it IS a reply, since the original invite
   never has these headers (it's the first message in its thread).
2. Plus-addressed Reply-To tag (yourinbox+<candidate_id>@gmail.com,
   see services/email_builder.py) - survives a client stripping
   threading headers or the subject being edited, since it's baked
   into the delivery address itself.
3. Subject-embedded token ([Ref:xxxxxxxx]) - the original mechanism,
   kept as a last-resort fallback. Since a subject alone can't prove
   genuineness (our own invite carries a token-shaped subject too),
   this path additionally requires is_threaded_reply.

Each signal is checked in order; the first one that resolves to a
known token wins.

This runs outside the FastAPI request lifecycle (the reply-monitoring
loop/CLI, not an HTTP handler), so it opens its own short-lived
session rather than using the app.core.deps.get_db() request
dependency - same per-call session lifecycle the original standalone
project used.
"""

import logging
from app.db.session import SessionLocal
from app.modules.email_outreach.repositories.email_repository import EmailRepository
from app.modules.email_outreach.services.email_parser import (
    parse_email_bytes,
    get_email_body,
    is_threaded_reply,
    extract_referenced_message_id,
    extract_plus_tag,
)
from app.modules.email_outreach.services.tracking_token_service import extract_token

log = logging.getLogger(__name__)


def resolve_reply_unfiltered(raw_email: bytes) -> dict:
    """
    Parse a raw email and resolve it to a candidate token, without
    checking a pending-tokens list - services/gmail_pubsub_backend.py
    (the only backend left; reply detection is push-only) resolves a
    push notification before its caller's current pending list is
    known, so pending-list filtering happens later in
    services/reply_tracker.py::check_for_replies instead.

    Args:
        raw_email (bytes): Raw email data.

    Returns:
        dict: {"token", "subject", "from", "body"} if resolved to any
            known token, otherwise None.
    """
    email_info = parse_email_bytes(raw_email)
    token = _resolve_token(email_info)

    if not token:
        return None

    return _build_result(email_info, token)


def _resolve_token(email_info: dict) -> str:
    """Try each signal in priority order; return the first token found."""
    with SessionLocal() as session:
        repo = EmailRepository(session)

        referenced_id = extract_referenced_message_id(email_info)
        if referenced_id:
            token = repo.get_token_by_message_id(referenced_id)
            if token:
                return token

        tag = extract_plus_tag(email_info)
        if tag:
            token = repo.get_token_by_candidate_id(tag)
            if token:
                return token

    subject_token = extract_token(email_info["subject"])
    if subject_token and is_threaded_reply(email_info):
        return subject_token

    return None


def _build_result(email_info: dict, token: str) -> dict:
    return {
        "token": token,
        "subject": email_info["subject"],
        "from": email_info["from"],
        "body": get_email_body(email_info["msg"]),
    }
