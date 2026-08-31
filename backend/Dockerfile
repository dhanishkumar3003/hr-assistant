FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Kokoro TTS model files — fetched at build time, not committed to git
ADD https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx ./kokoro-v1.0.int8.onnx
ADD https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin ./voices-v1.0.bin

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY app ./app

EXPOSE 8000