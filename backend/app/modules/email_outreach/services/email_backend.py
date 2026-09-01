"""
Email backend selector.

Two interchangeable backends, both exposing the same interface
(start, renew, send, fetch_unseen, stop):
  - gmail_pubsub_backend.GmailPubSubBackend - Gmail API send + Gmail
    push via Pub/Sub. The only reply-detection backend - see
    services/reply_tracker.py.
  - postal_backend.PostalBackend    - Postal HTTP API send only; no
    fetch (Postal has no message-fetch API) - pair with
    POST /email/webhook/reply for replies.

Selected by settings.email_backend ("gmail_pubsub" or "postal"), or
overridden per call (e.g. the CLI's --backend flag). services/sender.py
and services/reply_tracker.py only depend on this module, never on a
specific backend, so switching is a one-line settings/env change or
CLI flag.
"""

from app.core.config import settings

VALID_BACKENDS = ("gmail_pubsub", "postal")


def get_email_backend(backend_name: str = None):
    """
    Build an email backend.

    Args:
        backend_name (str): One of VALID_BACKENDS, or None to use
            settings.email_backend.

    Returns:
        GmailPubSubBackend or PostalBackend.
    """
    backend_name = backend_name or settings.email_backend

    if backend_name == "postal":
        from app.modules.email_outreach.services.postal_backend import PostalBackend
        return PostalBackend()

    from app.modules.email_outreach.services.gmail_pubsub_backend import GmailPubSubBackend
    return GmailPubSubBackend()
