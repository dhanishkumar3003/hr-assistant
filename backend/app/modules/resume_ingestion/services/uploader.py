"""
Module 1 - upload validation + hashing.

One job: look at the raw bytes HR sent and decide "acceptable or not",
then fingerprint them. No database, no disk, no HTTP in here.
"""

import hashlib
from dataclasses import dataclass
from pathlib import PurePath

from app.modules.resume_ingestion.models import FileType

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024                     # 10 MB - same number as ck_resumes_size_positive
ALLOWED_FILE_TYPES = frozenset(ft.value for ft in FileType)   # pdf / docx / doc / txt


class UploadValidationError(Exception):
    """A file that must be refused. `error` is the machine-readable code from the API contract."""

    def __init__(self, error: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.error = error
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedUpload:
    """A file that passed every check. Everything downstream works from this, never from the raw upload."""
    file_name: str      # original name, directory parts stripped
    file_type: str      # lowercase extension: pdf / docx / doc / txt
    content: bytes
    size_bytes: int
    sha256: str         # lowercase hex, 64 chars - the file's fingerprint


class FileValidator:
    """Applies the rules in the API contract: allowed type, not empty, at most 10 MB."""

    def validate(self, file_name: str, content: bytes) -> ValidatedUpload:
        clean_name = PurePath(file_name or "").name          # "C:\\x\\cv.pdf" -> "cv.pdf"
        if not clean_name:
            raise UploadValidationError("UNSUPPORTED_FILE_TYPE", "The upload has no file name.")

        file_type = _extension_of(clean_name)
        if file_type not in ALLOWED_FILE_TYPES:
            raise UploadValidationError(
                "UNSUPPORTED_FILE_TYPE",
                f"Only {', '.join(sorted(ALLOWED_FILE_TYPES))} are accepted, not '.{file_type or '?'}'.",
            )

        size = len(content)
        if size == 0:
            raise UploadValidationError("EMPTY_FILE", "The file is empty (0 bytes).")
        if size > MAX_FILE_SIZE_BYTES:
            raise UploadValidationError(
                "FILE_TOO_LARGE",
                f"The file is {size / (1024 * 1024):.1f} MB; the limit is 10 MB.",
                status_code=413,
            )

        return ValidatedUpload(
            file_name=clean_name,
            file_type=file_type,
            content=content,
            size_bytes=size,
            sha256=sha256_of(content),
        )


def sha256_of(content: bytes) -> str:
    """SHA-256 of the raw bytes, lowercase hex. Two identical files always give the same value."""
    return hashlib.sha256(content).hexdigest()


def _extension_of(file_name: str) -> str:
    suffix = PurePath(file_name).suffix          # ".PDF"
    return suffix[1:].lower() if suffix else ""  # "pdf"
