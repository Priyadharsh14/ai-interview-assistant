"""
Document Processing Service.

Orchestrates document validation, processor selection, and text extraction.
The single entry point for all document processing in the application.

This service lives in core/services/ because it contains business logic
(which processor to use, when to fail, what to return) even though it
delegates actual extraction to infrastructure/document_processing/.

Usage:
    service = DocumentProcessingService()
    result = service.process(file_path="./uploads/resume.pdf", original_filename="resume.pdf")
    print(result.raw_text)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from config.logging_config import get_logger
from core.interfaces.document_processor import (
    BaseDocumentProcessor,
    DocumentProcessingError,
    ExtractedDocument,
)
from infrastructure.document_processing.docx_processor import DOCXProcessor
from infrastructure.document_processing.file_validator import (
    FileValidationError,
    validate_uploaded_file,
)
from infrastructure.document_processing.pdf_processor import PDFProcessor

logger = get_logger(__name__)


class DocumentProcessingService:
    """
    Orchestrates document validation and text extraction.

    Selects the correct processor for each file type using the
    Registry pattern — processors register themselves by extension.

    Dependency injection: processors are passed in, making this
    class fully testable without real files.
    """

    def __init__(
        self,
        processors: list[BaseDocumentProcessor] | None = None,
    ) -> None:
        """
        Initialise with a list of processors.

        Args:
            processors: List of processor implementations.
                        Defaults to [PDFProcessor, DOCXProcessor].
        """
        self._processors: list[BaseDocumentProcessor] = processors or [
            PDFProcessor(),
            DOCXProcessor(),
        ]
        logger.debug(
            "DocumentProcessingService initialised",
            extra={"processors": [type(p).__name__ for p in self._processors]},
        )

    def process(
        self,
        file_path: str,
        original_filename: str,
    ) -> ExtractedDocument:
        """
        Validate, select processor, and extract text from a document.

        Args:
            file_path: Path to the saved file on disk.
            original_filename: Original filename as uploaded by the user.

        Returns:
            ExtractedDocument with cleaned text and metadata.

        Raises:
            FileValidationError: If the file fails validation.
            DocumentProcessingError: If text extraction fails.
        """
        logger.info(
            "Processing document",
            extra={"file": original_filename},
        )

        # Step 1: Validate (extension, size, magic bytes)
        extension = validate_uploaded_file(file_path, original_filename)

        # Step 2: Find the right processor
        processor = self._get_processor(extension)
        if processor is None:
            raise DocumentProcessingError(
                f"No processor found for '.{extension}' files."
            )

        # Step 3: Extract text
        document = processor.extract_text(file_path)

        logger.info(
            "Document processing complete",
            extra={
                "file": original_filename,
                "words": document.word_count,
                "method": document.extraction_method,
            },
        )

        return document

    def process_text_input(self, text: str, label: str = "text_input") -> ExtractedDocument:
        """
        Wrap plain text (e.g. a pasted Job Description) into an ExtractedDocument.

        Allows the same pipeline to handle both file uploads and direct text input.

        Args:
            text: Raw text content.
            label: Descriptive label used as the file_name.

        Returns:
            ExtractedDocument wrapping the provided text.
        """
        from infrastructure.document_processing.text_cleaner import (
            clean_extracted_text,
            count_words,
        )

        if not text or not text.strip():
            raise DocumentProcessingError("Text input cannot be empty.")

        cleaned = clean_extracted_text(text)
        return ExtractedDocument(
            file_name=label,
            file_path="",
            raw_text=cleaned,
            page_count=0,
            word_count=count_words(cleaned),
            extraction_method="text_input",
        )

    def _get_processor(self, extension: str) -> BaseDocumentProcessor | None:
        """Return the first processor that supports the given extension."""
        for processor in self._processors:
            if processor.supports(extension):
                return processor
        return None

    @property
    def supported_extensions(self) -> list[str]:
        """List all extensions handled by registered processors."""
        extensions = []
        for ext in ["pdf", "docx"]:
            for processor in self._processors:
                if processor.supports(ext):
                    extensions.append(ext)
                    break
        return extensions
