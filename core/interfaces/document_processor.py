"""
Document Processor Interface.

Abstract contract for document text extraction implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    """Result of text extraction from a document file."""

    file_name: str
    file_path: str
    raw_text: str
    page_count: int = 0
    word_count: int = 0
    extraction_method: str = ""


class BaseDocumentProcessor(ABC):
    """
    Abstract base for document processors (PDF, DOCX, etc.).

    Each concrete processor handles one file type.
    DocumentProcessingService uses the right processor
    based on file extension.
    """

    @abstractmethod
    def extract_text(self, file_path: str) -> ExtractedDocument:
        """
        Extract all text from a document file.

        Args:
            file_path: Absolute path to the document.

        Returns:
            ExtractedDocument with raw text and metadata.

        Raises:
            DocumentProcessingError: On extraction failure.
        """
        ...

    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """
        Return True if this processor handles the given extension.

        Args:
            file_extension: Lowercase extension without dot (e.g. 'pdf').
        """
        ...


class DocumentProcessingError(Exception):
    """Raised when document extraction fails."""
    pass
