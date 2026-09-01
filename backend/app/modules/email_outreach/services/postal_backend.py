"""
Postal (https://docs.postalserver.io/developer/api) HTTP send backend.

Postal is a send-only relay - it has no message-fetch API, so unlike
gmail_pubsub_backend.py, fetch_unseen() here can't detect replies at
all. Inbound replies still arrive via POST /email/webhook/reply (see
services/reply_tracker.py) regardless of which backend sends outbound
mail. Implements the same interface as the other backends (see
email_backend.py) so services/sender.py never needs to know which one
is active.
"""

import logging
from email.message import EmailMessage

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

POSTAL_SEND_TIMEOUT_SECONDS = 20


def _extract_html_body(message: EmailMessage) -> str:
    html_part = message.get_body(preferencelist=("html",))
    return html_part.get_content() if html_part else ""


def _extract_plain_body(message: EmailMessage) -> str:
    plain_part = message.get_body(preferencelist=("plain",))
    return plain_part.get_content() if plain_part else ""


class PostalBackend:
    """Send-only email backend using the Postal HTTP API."""

    def start(self) -> None:
        """No persistent connection needed for a stateless HTTP API."""

    def renew(self) -> None:
        """No registration to renew - Postal has no watch/subscription concept."""

    def send(self, message: EmailMessage) -> bool:
        """
        Send an email message via the Postal API.

        Args:
            message (EmailMessage): Email message to send (as built by
                services/email_builder.py - From/To/Subject/Message-ID/
                Reply-To headers plus plain+HTML bodies).

        Returns:
            bool: True if Postal accepted the message, False otherwise.
        """
        payload = {
            "to": [message["To"]],
            "from": settings.postal_sender_address or message["From"],
            "sender": settings.postal_sender_address or message["From"],
            "subject": message["Subject"],
            "plain_body": _extract_plain_body(message),
            "html_body": _extract_html_body(message),
        }

        reply_to = message.get("Reply-To")
        if reply_to:
            payload["reply_to"] = reply_to

        try:
            response = httpx.post(
                settings.postal_api_url,
                json=payload,
                headers={
                    "X-Server-API-Key": settings.postal_api_key,
                    "Content-Type": "application/json",
                },
                timeout=POSTAL_SEND_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            log.error(f"Postal send failed for {message['To']}: {exc!r}")
            return False

        if body.get("status") != "success":
            log.error(f"Postal rejected message for {message['To']}: {body}")
            return False

        log.debug(f"Message sent via Postal to {message['To']}")
        return True

    def fetch_unseen(self, pending_tokens: list) -> list:
        """
        Postal has no message-fetch API - reply detection for this
        backend is handled entirely outside of it, via the
        /email/webhook/reply endpoint. Always returns no matches so
        the shared monitor loop in reply_tracker.py stays a no-op if
        it's ever pointed at this backend.
        """
        return []

    def stop(self) -> None:
        """No persistent connection to close."""
