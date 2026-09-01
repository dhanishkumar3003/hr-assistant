"""
Gmail API send.

send_message is the raw Gmail API send operation, reused by
gmail_pubsub_backend.GmailPubSubBackend (the only backend left that
uses it - see email_backend.py). Reply detection is push-only now
(GmailPubSubBackend's Pub/Sub listener, or POST /email/webhook/reply) -
there is no polling backend left to adapt this into.
"""

import base64
import logging
from email.message import EmailMessage
from app.modules.email_outreach.services.gmail_auth_service import get_gmail_service

log = logging.getLogger(__name__)


def send_message(message: EmailMessage) -> bool:
    """
    Send an email message through the Gmail API.

    Args:
        message (EmailMessage): Email message to send.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")
        get_gmail_service().users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()

        log.debug(f"Message sent to {message['To']}")
        return True

    except Exception as e:
        log.error(f"Gmail API send failed for {message['To']}: {e!r}")
        return False
