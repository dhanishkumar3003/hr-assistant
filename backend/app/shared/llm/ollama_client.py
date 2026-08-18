import json
import httpx

from app.core.config import settings
from app.shared.interfaces.llm_service import ILLMService


class OllamaLLMService(ILLMService):
    def __init__(self, model: str | None = None):
        self._base_url = settings.ollama_base_url
        self._model = model or settings.llm_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        strict_system = system_prompt + "\n\nRespond ONLY with valid JSON. No preamble, no markdown fences."
        raw = self.complete(strict_system, user_prompt)
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)