"""
Module 1 - where the uploaded FILE bytes live.

IFileStorage is the contract; LocalDiskStorage is the only implementation for
the POC. An S3Storage can be added later as a new class without touching any
caller (Open/Closed).

Paths returned by save() and stored in resumes.file_path are RELATIVE to the
upload root, e.g. "2026/08/3f9c...b1.pdf". That keeps them valid whether the
backend runs on Windows, in Docker (/app/app/uploads) or on a laptop.
"""

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path


class IFileStorage(ABC):
    @abstractmethod
    def save(self, content: bytes, file_type: str) -> str:
        """Store the bytes; return the relative path to record in resumes.file_path."""

    @abstractmethod
    def get(self, file_path: str) -> bytes:
        """Read the bytes back for a path previously returned by save()."""

    @abstractmethod
    def delete(self, file_path: str) -> None:
        """Remove the file. Must not fail if it is already gone."""


#  backend/app/uploads  - already listed in .gitignore, and inside the folder
#  docker-compose mounts, so files written in the container land on the host.
DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads"


class LocalDiskStorage(IFileStorage):
    """Writes to <root>/YYYY/MM/<random>.<ext>. Root = $UPLOAD_DIR or backend/app/uploads."""

    def __init__(self, root: Path | None = None):
        self._root = root or Path(os.environ.get("UPLOAD_DIR", DEFAULT_UPLOAD_ROOT))

    def save(self, content: bytes, file_type: str) -> str:
        now = datetime.now(timezone.utc)
        relative = Path(f"{now:%Y}") / f"{now:%m}" / f"{uuid.uuid4().hex}.{file_type}"
        full = self._root / relative
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
        return relative.as_posix()          # forward slashes, always

    def get(self, file_path: str) -> bytes:
        return (self._root / file_path).read_bytes()

    def delete(self, file_path: str) -> None:
        (self._root / file_path).unlink(missing_ok=True)
