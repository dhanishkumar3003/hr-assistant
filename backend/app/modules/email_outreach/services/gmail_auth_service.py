"""
Gmail OAuth authentication.

credentials.json (OAuth client) and token.json (granted access/refresh
token, created on first run) live at the email_outreach module root -
gitignore both, never commit them.
"""

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


MODULE_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = MODULE_ROOT / "credentials.json"
TOKEN_FILE = MODULE_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

# Cached across calls - the Pub/Sub backend calls this on every
# notification (potentially several per second under backlog), and
# rebuilding the OAuth + discovery-document dance from scratch each
# time is pure overhead once the access token is still valid.
_cached_creds = None
_cached_service = None


def get_gmail_service():
    global _cached_creds, _cached_service

    if _cached_creds and _cached_creds.valid:
        return _cached_service

    creds = None

    if TOKEN_FILE.exists():
        # Read the scopes actually granted to the stored refresh token
        # directly from the file. Credentials.from_authorized_user_file(
        # path, SCOPES) sets creds.scopes to whatever SCOPES you pass it,
        # regardless of what the token was really issued for - so
        # checking creds.scopes always "passes" even when the real grant
        # is narrower, and a stale token then fails with a confusing
        # invalid_scope error on refresh() instead of prompting a fresh
        # consent here.
        stored = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        granted_scopes = set(stored.get("scopes", []))

        if set(SCOPES).issubset(granted_scopes):
            creds = Credentials.from_authorized_user_file(
                str(TOKEN_FILE),
                SCOPES
            )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE),
                SCOPES
            )

            creds = flow.run_local_server(port=0)

        with TOKEN_FILE.open("w", encoding="utf-8") as token:
            token.write(creds.to_json())

    _cached_creds = creds
    _cached_service = build(
        "gmail",
        "v1",
        credentials=creds,
        # Suppresses the harmless but noisy "file_cache is only
        # supported with oauth2client<4.0.0" warning logged on every
        # build() call otherwise.
        cache_discovery=False,
    )
    return _cached_service
