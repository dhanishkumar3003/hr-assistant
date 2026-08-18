from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

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
    llm_model: str = "gpt-oss:120b-cloud"
    ollama_base_url: str = "http://localhost:11434"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"


settings = Settings()