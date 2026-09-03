"""
Module 1 - pulling the WORDS out of a resume file.

One extractor class per file format (Single Responsibility). The registry
picks the right one by file type, so adding a new format = one new class
registered in default_registry(), nothing else changes (Open/Closed).

Every extractor takes bytes and returns plain text. Nothing here touches the
database or the disk.
"""

import io
from abc import ABC, abstractmethod

from docx import Document as _load_docx                 # python-docx
from pypdf import PdfReader
from pypdf.errors import PyPdfError


class TextExtractionError(Exception):
    """The file was accepted but its text cannot be read. The message becomes resumes.failure_reason."""


class ITextExtractor(ABC):
    @abstractmethod
    def supports(self, file_type: str) -> bool: ...

    @abstractmethod
    def extract(self, content: bytes) -> str:
        """Return the text, or raise TextExtractionError with a human-readable reason."""


class PdfExtractor(ITextExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == "pdf"

    def extract(self, content: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                # Some PDFs are "encrypted" with an empty password; try that first.
                if reader.decrypt("") == 0:
                    raise TextExtractionError("PDF is password protected - no text could be extracted")
            pages = [page.extract_text() or "" for page in reader.pages]
        except TextExtractionError:
            raise
        except PyPdfError as exc:
            raise TextExtractionError(f"PDF could not be read: {exc}") from exc
        return "\n".join(pages).strip()


class DocxExtractor(ITextExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == "docx"

    def extract(self, content: bytes) -> str:
        try:
            document = _load_docx(io.BytesIO(content))
        except Exception as exc:                        # python-docx raises several unrelated types
            raise TextExtractionError(f"DOCX could not be read: {exc}") from exc

        parts = [p.text for p in document.paragraphs if p.text.strip()]
        for table in document.tables:                   # skills tables are common in resumes
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts).strip()


class TxtExtractor(ITextExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == "txt"

    def extract(self, content: bytes) -> str:
        return content.decode("utf-8", errors="replace").strip()


#  NOTE: there is deliberately no extractor for legacy ".doc". The upload is
#  accepted (the contract allows the type) but processing marks it FAILED with
#  a "convert to .docx" reason. See API contract open question 3.


class ExtractorRegistry:
    """Finds the extractor for a file type. Returns None when nobody supports it."""

    def __init__(self, extractors: list[ITextExtractor]):
        self._extractors = list(extractors)

    def for_type(self, file_type: str) -> ITextExtractor | None:
        for extractor in self._extractors:
            if extractor.supports(file_type):
                return extractor
        return None


def default_registry() -> ExtractorRegistry:
    """The one place that lists the concrete extractors."""
    return ExtractorRegistry([PdfExtractor(), DocxExtractor(), TxtExtractor()])
