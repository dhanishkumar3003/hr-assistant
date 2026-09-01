"""
Email parsing - extracting structured data from raw received email bytes.

Split out of a combined "email_handler" module: this half only ever
reads an incoming email; services/email_builder.py only ever builds one
going out. Neither depends on the other.
"""

import email
import re
import logging

log = logging.getLogger(__name__)

# Where a quoted/forwarded original message typically starts. Most mail
# clients append the full original email below a reply, and our own
# invitation/confirmation emails contain words like "decline" (the
# button label) - left in, that quoted boilerplate gets scanned by the
# classifier right alongside what the candidate actually wrote and can
# flip the result (see strip_quoted_content).
_QUOTE_START_PATTERNS = [
    re.compile(r"^\s*On .{0,120} wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*From:\s*.+$", re.MULTILINE),
    re.compile(r"^>", re.MULTILINE),
]


def strip_quoted_content(body: str) -> str:
    """
    Cut a reply body off at the start of any quoted/forwarded content.

    Args:
        body (str): Raw reply body text.

    Returns:
        str: Only the text before the first quote marker, stripped -
            this is both what gets classified and what gets stored (see
            services/reply_tracker.py::process_reply).
    """
    text = body or ""
    earliest = len(text)

    for pattern in _QUOTE_START_PATTERNS:
        match = pattern.search(text)
        if match and match.start() < earliest:
            earliest = match.start()

    return text[:earliest].strip()


def get_email_body(msg) -> str:
    """
    Extract plain text body from email message.

    Handles both multipart and simple emails, preferring
    plain text content and skipping attachments.

    Args:
        msg: Email message object from email.message_from_bytes().

    Returns:
        str: Plain text body content, or empty string if none found.
    """
    if msg.is_multipart():
        # For multipart emails, find the plain text part
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if (
                content_type == "text/plain"
                and "attachment" not in content_disposition
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")

        return ""

    # For simple emails, extract payload directly
    payload = msg.get_payload(decode=True)
    return (
        payload.decode(errors="ignore")
        if payload
        else ""
    )


def parse_email_bytes(raw_email: bytes) -> dict:
    """
    Parse raw email bytes into a structured message.

    Args:
        raw_email (bytes): Raw email data.

    Returns:
        dict: Dictionary with 'msg' (email message object), 'from'
            (sender), 'subject', 'in_reply_to', 'references', 'to',
            'delivered_to' keys.
    """
    msg = email.message_from_bytes(raw_email)
    return {
        "msg": msg,
        "from": msg.get("From", ""),
        "subject": msg.get("Subject", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
        "references": msg.get("References", ""),
        "to": msg.get("To", ""),
        "delivered_to": msg.get("Delivered-To", ""),
    }


def is_threaded_reply(email_info: dict) -> bool:
    """
    Whether a parsed message is actually threaded as a reply.

    A sent invitation carries a tracking token in its subject too, so
    subject matching alone can't tell it apart from an actual reply -
    this matters most when testing by sending to your own address,
    where the invite lands right back in the same inbox as the reply.
    Real replies always set In-Reply-To/References (every mail client
    does this automatically); the original message never does, since
    it's the first thing in the thread.

    Args:
        email_info (dict): Result of parse_email_bytes().

    Returns:
        bool: True if this message threads back to an earlier one.
    """
    return bool(email_info.get("in_reply_to") or email_info.get("references"))


_MESSAGE_ID_PATTERN = re.compile(r"<[^<>]+>")
_PLUS_TAG_PATTERN = re.compile(r"[\w.+-]+\+([a-zA-Z0-9-]+)@")


def extract_referenced_message_id(email_info: dict) -> str:
    """
    Extract the Message-ID this email is replying to, if any.

    Prefers In-Reply-To (the immediate parent); falls back to the last
    entry in References (the full ancestor chain, most immediate last)
    if In-Reply-To is missing.

    Args:
        email_info (dict): Result of parse_email_bytes().

    Returns:
        str: The referenced Message-ID (with angle brackets, matching
            how it's stored - see services/sender.py), or None.
    """
    in_reply_to = (email_info.get("in_reply_to") or "").strip()
    if in_reply_to:
        return in_reply_to

    references = email_info.get("references") or ""
    ids = _MESSAGE_ID_PATTERN.findall(references)
    return ids[-1] if ids else None


def extract_plus_tag(email_info: dict) -> str:
    """
    Extract a plus-addressing tag from the recipient address, if any.

    Looks at Delivered-To first (stamped server-side by Gmail's own
    MTA, so it's consistent regardless of the sending mail client),
    then falls back to the To header (what a client's Reply typically
    copies from our Reply-To). See services/email_builder.py for where
    the tag (yourinbox+<candidate_id>@gmail.com) is set.

    Args:
        email_info (dict): Result of parse_email_bytes().

    Returns:
        str: The tag value (the candidate_id), or None if the
            recipient address has no "+tag".
    """
    for header in ("delivered_to", "to"):
        match = _PLUS_TAG_PATTERN.search(email_info.get(header) or "")
        if match:
            return match.group(1)
    return None
