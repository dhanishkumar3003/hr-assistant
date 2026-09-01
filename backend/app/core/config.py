from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env - anchored on this file's location (not cwd), so it
# resolves the same whether uv/alembic/uvicorn run from backend/ or
# repo root, instead of a relative "../.env" silently picking up an
# unrelated .env at the repo root.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str
    llm_api_key: str = ""
    llm_base_url: str = ""
    stt_api_key: str = ""
    stt_provider: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_tenant_id: str = ""
    graph_sender_mailbox: str = ""
    env: str = "local"
    secret_key: str = "changeme"
    candidate_token_expiry_minutes: int = 4320

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"

    # email_outreach module - Gmail API + Pub/Sub transport, ported
    # from a standalone project. graph_* above is for the eventual MS
    # Graph transport; this module still sends via Gmail, so these are
    # additive rather than a replacement. Reply detection is push-only
    # (Gmail Pub/Sub, or POST /email/webhook/reply) - no polling backend.
    gmail_address: str = ""
    email_backend: str = "gmail_pubsub"  # "gmail_pubsub" | "postal"
    gmail_pubsub_topic: str = ""
    gmail_pubsub_subscription: str = ""
    candidate_source: str = "json"  # "json" | "api"
    company_name: str = "ChangePond Technologies"
    testdata_json_path: str = "app/tests/modules/email_outreach/testdata.json"
    response_server_base_url: str = "http://localhost:8000"

    # Postal (https://docs.postalserver.io/developer/api) - HTTP send-only
    # transport. Postal has no reply-fetch API of its own; inbound replies
    # still arrive via POST /email/webhook/reply regardless of which
    # backend sends outbound mail.
    postal_api_url: str = ""  # e.g. https://postal.example.com/api/v1/send/message
    postal_api_key: str = ""
    postal_sender_address: str = ""

    # Response-threshold auto-inactive job (Module 3: "tracks replies
    # against a configurable response threshold... non-responders are
    # auto-marked inactive").
    response_threshold_hours: int = 72


settings = Settings()