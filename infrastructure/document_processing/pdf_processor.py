"""
PDF Document Processor.

Concrete implementation of BaseDocumentProcessor for PDF files.
Uses pypdf for extraction with page-level metadata tracking.

Design decisions:
- Extract page-by-page to preserve structure metadata
- Attempt layout-aware extraction first, fall back to simple extraction
- Never raise on partial extraction — return what we can with a warning
"""

from __future__ import annotations

import os
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from config.logging_config import get_logger
from core.interfaces.document_processor import (
    BaseDocumentProcessor,
    DocumentProcessingError,
    ExtractedDocument,
)
from infrastructure.document_processing.text_cleaner import (
    clean_extracted_text,
    count_words,
    truncate_text,
)

logger = get_logger(__name__)


class PDFProcessor(BaseDocumentProcessor):
    """
    PDF text extractor using pypdf.

    Handles standard text-based PDFs. Scanned/image-only PDFs
    will return minimal text — OCR support is a future enhancement.
    """

    SUPPORTED_EXTENSION = "pdf"
    MAX_CHARS = 100_000  # ~20,000 words — enough for any resume or JD

    def supports(self, file_extension: str) -> bool:
        """Return True for 'pdf' extension."""
        return file_extension.lower().strip(".") == self.SUPPORTED_EXTENSION

    def extract_text(self, file_path: str) -> ExtractedDocument:
        """
        Extract and clean text from a PDF file.

        Args:
            file_path: Absolute or relative path to the PDF.

        Returns:
            ExtractedDocument with cleaned text and page count.

        Raises:
            DocumentProcessingError: If the file cannot be read.
        """
        path = Path(file_path)
        self._validate_file(path)

        logger.info("Extracting PDF", extra={"file": path.name})

        try:
            reader = PdfReader(str(path))
            page_count = len(reader.pages)
            raw_pages: list[str] = []

            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    raw_pages.append(page_text)
                except Exception as e:
                    logger.warning(
                        "Failed to extract page — skipping",
                        extra={"page": page_num + 1, "error": str(e)},
                    )
                    raw_pages.append("")

            raw_text = "\n\n".join(page for page in raw_pages if page.strip())

            if not raw_text.strip():
                raise DocumentProcessingError(
                    f"No text could be extracted from '{path.name}'. "
                    "The PDF may be scanned or image-based."
                )

            cleaned = clean_extracted_text(raw_text)
            cleaned = truncate_text(cleaned, self.MAX_CHARS)
            word_count = count_words(cleaned)

            logger.info(
                "PDF extraction complete",
                extra={"file": path.name, "pages": page_count, "words": word_count},
            )

            return ExtractedDocument(
                file_name=path.name,
                file_path=str(path.resolve()),
                raw_text=cleaned,
                page_count=page_count,
                word_count=word_count,
                extraction_method="pypdf",
            )

        except DocumentProcessingError:
            raise
        except PdfReadError as e:
            raise DocumentProcessingError(
                f"'{path.name}' is not a valid or readable PDF: {e}"
            ) from e
        except Exception as e:
            logger.error("Unexpected PDF extraction error", extra={"error": str(e)})
            raise DocumentProcessingError(
                f"Failed to process '{path.name}': {e}"
            ) from e

    def _validate_file(self, path: Path) -> None:
        """Validate that the file exists and is a PDF."""
        if not path.exists():
            raise DocumentProcessingError(f"File not found: '{path}'")
        if not path.is_file():
            raise DocumentProcessingError(f"Path is not a file: '{path}'")
        if path.suffix.lower() != ".pdf":
            raise DocumentProcessingError(
                f"Expected a .pdf file, got: '{path.suffix}'"
            )
        if path.stat().st_size == 0:
            raise DocumentProcessingError(f"File is empty: '{path.name}'")
