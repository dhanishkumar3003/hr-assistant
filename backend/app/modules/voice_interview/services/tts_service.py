from abc import ABC, abstractmethod


class ITTSProvider(ABC):
    @abstractmethod
    def speak(self, text: str, output_path: str) -> str:
        ...


class KokoroTTSProvider(ITTSProvider):
    def __init__(self, model_path: str = "kokoro-v1.0.int8.onnx", voices_path: str = "voices-v1.0.bin"):
        from kokoro_onnx import Kokoro
        self.kokoro = Kokoro(model_path, voices_path)

    def speak(self, text: str, output_path: str) -> str:
        import soundfile as sf
        samples, sample_rate = self.kokoro.create(text, voice="af_sarah", speed=1.0, lang="en-us")
        sf.write(output_path, samples, sample_rate)
        return output_path


def get_tts_provider() -> ITTSProvider:
    return KokoroTTSProvider()