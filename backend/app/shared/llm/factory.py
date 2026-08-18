from functools import lru_cache

from app.core.config import settings
from app.shared.interfaces.llm_service import ILLMService
from app.shared.llm.ollama_client import OllamaLLMService
# from app.shared.llm.anthropic_client import AnthropicLLMService


@lru_cache
def get_llm_service() -> ILLMService:
    """Single entry point every module uses to get an LLM client.
    Never import OllamaLLMService/AnthropicLLMService directly outside this file —
    always call get_llm_service() so switching provider is a .env change only.
    """
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        return OllamaLLMService()
    # if provider == "anthropic":
    #     return AnthropicLLMService()

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Supported: ollama, anthropic")