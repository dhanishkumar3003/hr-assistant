from abc import ABC, abstractmethod
import os


class ISTTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, prompt: str = "") -> str:
        ...


class GroqSTTProvider(ISTTProvider):
    def __init__(self, api_key: str):
        from groq import Groq
        self.client = Groq(api_key=api_key)

    def transcribe(self, audio_path: str, prompt: str = "") -> str:
        with open(audio_path, "rb") as f:
            result = self.client.audio.transcriptions.create(
                file=f,
                model="whisper-large-v3-turbo",
                prompt=prompt,
            )
        return result.text


class WhisperLocalProvider(ISTTProvider):
    def __init__(self, model_size: str = "small"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str, prompt: str = "") -> str:
        segments, _ = self.model.transcribe(audio_path, initial_prompt=prompt)
        return "".join(s.text for s in segments)


def get_stt_provider() -> ISTTProvider:
    from app.core.config import settings
    if settings.stt_provider == "groq":
        return GroqSTTProvider(api_key=settings.stt_api_key)
    return WhisperLocalProvider(model_size="small")