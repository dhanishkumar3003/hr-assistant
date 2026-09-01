"""
Reply monitoring loop.

Listens for push notifications of replies to sent invitations, matches
them to candidates via token, and classifies them. Backend-agnostic -
see email_backend.py for the Pub/Sub vs Postal switch. Reply detection
is push-only: GmailPubSubBackend.fetch_unseen blocks on its internal
queue until Gmail pushes a notification (no polling delay);
PostalBackend.fetch_unseen always returns immediately with no matches
(Postal has no fetch API - see POST /email/webhook/reply instead).
"""

import time
import logging
from datetime import datetime, timezone

from app.modules.email_outreach.repositories.email_repository import IEmailRepository
from app.modules.email_outreach.services.sender import EmailSenderService
from app.modules.email_outreach.services.email_backend import get_email_backend
from app.modules.email_outreach.services.email_parser import strip_quoted_content
from app.modules.email_outreach.services.reply_classifier import classify_reply_with_source

log = logging.getLogger(__name__)

MAX_MONITOR_MINUTES = 60

# PostalBackend.fetch_unseen returns instantly with no matches every
# call (Postal has no fetch API - see email_backend.py) - without a
# wait, the loop would busy-spin at CPU-max checking get_pending_tokens
# in a tight cycle. GmailPubSubBackend needs no such wait: its
# fetch_unseen already blocks internally on the Pub/Sub queue.
IDLE_BACKEND_WAIT_SECONDS = 15

# Gmail's watch() registration (GmailPubSubBackend.renew) expires after
# 7 days regardless of activity. A daily renewal cadence gives ample
# margin without hammering the API - see monitor_forever below.
RENEW_INTERVAL_SECONDS = 24 * 60 * 60


class ReplyTrackerService:
    """
    Listens for push notifications from an email backend for replies,
    classifies them, and sends a confirmation. Depends only on
    IEmailRepository and EmailSenderService - swap the concrete
    repository or backend without touching this class.
    """

    def __init__(
        self,
        email_repo: IEmailRepository,
        sender: EmailSenderService,
        backend_name: str = None,
    ):
        self._email_repo = email_repo
        self._sender = sender
        self._backend_name = backend_name

    def process_reply(self, token: str, subject: str, body: str, received_at: datetime) -> str:
        """
        Record, classify and confirm a single detected reply.

        Shared endpoint for both delivery mechanisms this module
        supports - the Pub/Sub push loop (monitor_replies below) and
        the webhook (api.py POST /email/webhook/reply) - so wiring in a
        real mail-provider webhook is a matter of calling this method
        with the parsed payload, not duplicating the record/classify/
        confirm sequence.

        Args:
            token (str): Tracking token the reply matched to.
            subject (str): Reply subject line.
            body (str): Reply body text.
            received_at (datetime): When the reply was received.

        Returns:
            str: The classification result.
        """
        # Cut the body down to what the candidate actually wrote before
        # storing it - most mail clients paste the entire quoted
        # original message below a reply, and nobody reading this back
        # later (a dashboard, a status/history view) wants to scroll
        # past our own invite to find the one line someone typed.
        clean_body = strip_quoted_content(body) or (body or "")
        self._email_repo.record_reply(token, subject, clean_body, received_at)

        reply_body = self._email_repo.get_reply_body(token)
        classification, source = classify_reply_with_source(reply_body)
        self._email_repo.set_classification(token, classification, datetime.now(timezone.utc), source)

        log.info(f"Classified token={token} as '{classification}' (source={source})")

        self._sender.send_confirmation(token, classification)

        return classification

    def check_for_replies(self, backend, pending_tokens: list) -> list:
        """
        Check for new replies pushed by the backend and match them to candidates.

        Args:
            backend: Active email backend (see email_backend.py).
            pending_tokens (list): Tokens currently awaiting a reply.

        Returns:
            list: List of tokens that matched new replies.
        """
        matched_tokens = []

        for reply in backend.fetch_unseen(pending_tokens):
            token = reply["token"]

            # Verify sender
            expected_email = self._email_repo.get_candidate_email(token)
            if expected_email.lower() not in reply["from"].lower():
                log.warning(
                    f"Token {token} matched but "
                    f"sender mismatch: "
                    f"expected {expected_email}, "
                    f"got {reply['from']}. "
                    f"Recording anyway."
                )

            log.info(
                f"Reply detected | "
                f"token={token} | "
                f"from={reply['from']} | "
                f"subject='{reply['subject']}'"
            )

            self.process_reply(
                token, reply["subject"], reply["body"], datetime.now(timezone.utc)
            )

            matched_tokens.append(token)

        return matched_tokens

    def monitor_replies(self) -> None:
        """
        Run the main monitoring loop.

        Waits on push notifications for replies to pending invitations,
        classifies them, sends a confirmation, and updates state. Runs
        until all candidates have replied or timeout is reached.
        """
        pending_tokens = self._email_repo.get_pending_tokens()

        if not pending_tokens:
            log.info(
                "No pending candidates to monitor "
                "(nothing with status='sent')."
            )
            return

        log.info(
            f"Monitoring {len(pending_tokens)} "
            f"pending candidate(s) for replies..."
        )

        backend = get_email_backend(self._backend_name)
        backend.start()
        start_time = time.time()
        timeout_seconds = MAX_MONITOR_MINUTES * 60

        try:
            while True:
                still_pending = self._email_repo.get_pending_tokens()

                if not still_pending:
                    log.info(
                        "All tracked candidates have replied. Done."
                    )
                    break

                if time.time() - start_time > timeout_seconds:
                    log.warning(
                        f"Monitor timeout reached "
                        f"({MAX_MONITOR_MINUTES} min). "
                        f"Still pending: {still_pending}"
                    )
                    break

                matched = self.check_for_replies(backend, still_pending)

                # GmailPubSubBackend.fetch_unseen already blocked
                # internally above, so this is a no-op there. Only
                # PostalBackend (which never blocks, never matches)
                # needs an explicit wait to avoid busy-spinning.
                if not matched and not getattr(backend, "BLOCKS_ON_FETCH", False):
                    time.sleep(IDLE_BACKEND_WAIT_SECONDS)

        finally:
            backend.stop()

    def monitor_forever(self, stop_event=None) -> None:
        """
        Run the monitoring loop indefinitely - for a long-running
        server process (see app.main's startup hook), as opposed to
        monitor_replies' one-shot/timeout behavior for manual CLI use.

        Never exits on an empty pending list (a new candidate can be
        sent an invite at any time while this runs) and has no overall
        timeout. Periodically calls backend.renew() so a push
        registration that expires after a fixed window (Gmail's 7-day
        watch() limit) keeps working indefinitely.

        Args:
            stop_event (threading.Event): If given, checked each loop
                iteration - setting it lets the caller shut this down
                cleanly (e.g. on app shutdown) instead of only ever
                exiting via an uncaught exception.
        """
        log.info("Starting continuous reply monitor...")

        backend = get_email_backend(self._backend_name)
        backend.start()
        last_renewed = time.time()

        try:
            while not (stop_event and stop_event.is_set()):
                if time.time() - last_renewed > RENEW_INTERVAL_SECONDS:
                    backend.renew()
                    last_renewed = time.time()

                pending_tokens = self._email_repo.get_pending_tokens()

                if not pending_tokens:
                    time.sleep(IDLE_BACKEND_WAIT_SECONDS)
                    continue

                matched = self.check_for_replies(backend, pending_tokens)

                if not matched and not getattr(backend, "BLOCKS_ON_FETCH", False):
                    time.sleep(IDLE_BACKEND_WAIT_SECONDS)

        finally:
            backend.stop()
