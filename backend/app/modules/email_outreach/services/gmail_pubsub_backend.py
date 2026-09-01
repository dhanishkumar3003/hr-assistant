"""
Gmail API + Pub/Sub push email backend.

Sends via the Gmail API (reused from gmail_backend.py). Reply detection
uses Gmail's watch() push mechanism instead of polling: Gmail publishes
a notification to a Pub/Sub topic the instant the inbox changes. This
backend keeps a streaming pull open on that subscription (not a
periodic pull) - a background thread wakes up immediately when a
notification arrives, resolves it to actual new messages via
history.list(), and hands matching replies to services/reply_tracker.py
the moment they're available instead of waiting for the next poll tick.

Requires one-time GCP setup (Pub/Sub topic + subscription + IAM grant
for Gmail's push service account, plus Application Default Credentials
for the Pub/Sub client). Adapts to the same backend interface as
PostalBackend (see email_backend.py), so switching to it is a one-line
settings.email_backend="gmail_pubsub" change.
"""

import base64
import logging
import queue
import threading
from email.message import EmailMessage
from google.cloud import pubsub_v1
from app.core.config import settings
from app.modules.email_outreach.services.gmail_auth_service import get_gmail_service
from app.modules.email_outreach.services.gmail_backend import send_message
from app.modules.email_outreach.services.reply_matcher import resolve_reply_unfiltered

log = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 15


class GmailPubSubBackend:
    """Email backend using Gmail API send + Gmail push via Pub/Sub."""

    # services/reply_tracker.py skips its extra sleep for backends that
    # already block inside fetch_unseen - this one waits on an internal
    # queue fed by a live streaming pull, so there's nothing extra to
    # wait for.
    BLOCKS_ON_FETCH = True

    def __init__(self):
        self._subscriber = None
        self._streaming_future = None
        self._history_id = None
        self._history_lock = threading.Lock()
        self._queue = queue.Queue()

    def start(self) -> None:
        """
        Register the Gmail watch and open a streaming Pub/Sub pull.

        The streaming pull runs on a background thread managed by the
        Pub/Sub client library; _on_message fires the instant a
        notification arrives, no polling loop involved.
        """
        self.renew()

        self._subscriber = pubsub_v1.SubscriberClient()
        self._streaming_future = self._subscriber.subscribe(
            settings.gmail_pubsub_subscription, callback=self._on_message
        )
        log.info(f"Streaming pull started | subscription={settings.gmail_pubsub_subscription}")

    def renew(self) -> None:
        """
        (Re-)register the Gmail watch.

        Gmail's watch() expires after 7 days regardless of activity -
        called once in start() and then periodically by
        services/reply_tracker.py::monitor_replies for a long-running
        listener, so push notifications don't silently stop after a
        week. Re-registering is idempotent (Gmail just extends the
        existing watch), so calling it early/often is harmless.
        """
        response = get_gmail_service().users().watch(
            userId="me",
            body={"topicName": settings.gmail_pubsub_topic, "labelIds": ["INBOX"]},
        ).execute()

        self._history_id = response["historyId"]
        log.info(
            f"Gmail watch registered | "
            f"historyId={self._history_id} | "
            f"expiration={response.get('expiration')}"
        )

    def send(self, message: EmailMessage) -> bool:
        """Send an email via the Gmail API."""
        return send_message(message)

    def fetch_unseen(self, pending_tokens: list) -> list:
        """
        Wait for the next push notification and return matching replies.

        Blocks up to POLL_INTERVAL_SECONDS for something to arrive on
        the internal queue fed by the streaming pull's background
        thread, but returns immediately the moment a match shows up -
        this is what makes it push rather than polling.

        Args:
            pending_tokens (list): Tokens currently awaiting a reply.

        Returns:
            list: Matching replies as {"token", "subject", "from", "body"}.
        """
        replies = []

        try:
            replies.append(self._queue.get(timeout=POLL_INTERVAL_SECONDS))
        except queue.Empty:
            return []

        # Drain anything else already waiting so a burst of replies
        # doesn't trickle out one per loop iteration.
        while True:
            try:
                replies.append(self._queue.get_nowait())
            except queue.Empty:
                break

        return [reply for reply in replies if reply["token"] in pending_tokens]

    def _on_message(self, message) -> None:
        """
        Streaming pull callback - runs on a Pub/Sub client thread the
        instant a notification is delivered.
        """
        try:
            for reply in self._resolve_new_messages():
                self._queue.put(reply)
        except Exception as e:
            log.error(f"Failed to resolve push notification: {e!r}")
        finally:
            # Ack regardless of outcome - history_id bookkeeping makes
            # this idempotent, and NOT acking would just redeliver the
            # same notification forever on a persistent failure.
            message.ack()

    def _resolve_new_messages(self) -> list:
        """
        Use history.list() to find messages added since the last check.

        Guarded by a lock since the Pub/Sub client can run multiple
        callbacks concurrently - without it, two notifications arriving
        close together could race on self._history_id and either miss
        messages or process the same one twice.
        """
        with self._history_lock:
            service = get_gmail_service()

            try:
                history = service.users().history().list(
                    userId="me",
                    startHistoryId=self._history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                ).execute()
            except Exception as e:
                log.error(f"Gmail history.list failed: {e!r}")
                return []

            message_ids = {
                added["message"]["id"]
                for record in history.get("history", [])
                for added in record.get("messagesAdded", [])
            }

            if "historyId" in history:
                self._history_id = history["historyId"]

            replies = []
            for message_id in message_ids:
                raw = service.users().messages().get(
                    userId="me",
                    id=message_id,
                    format="raw",
                ).execute()

                # reply_matcher runs the same Message-ID/plus-tag/subject-
                # token resolution used by every other backend, just
                # without filtering by pending_tokens yet - that happens
                # later in fetch_unseen once it knows the current list.
                reply = resolve_reply_unfiltered(base64.urlsafe_b64decode(raw["raw"]))
                if reply:
                    replies.append(reply)

            return replies

    def stop(self) -> None:
        """Stop the streaming pull and close the subscriber."""
        if self._streaming_future:
            self._streaming_future.cancel()
            self._streaming_future.result()
        if self._subscriber:
            self._subscriber.close()
