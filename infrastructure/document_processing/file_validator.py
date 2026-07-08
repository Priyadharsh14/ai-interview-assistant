"""
File Validator.

Validates uploaded files before they reach document processors.
Checks extension, size, and basic magic bytes to prevent processing
unexpected file types.
"""

from __future__ import annotations

import os
from pathlib import Path

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

# PDF magic bytes: %PDF
PDF_MAGIC = b"%PDF"
# DOCX magic bytes: PK (ZIP archive — DOCX is a zip)
DOCX_MAGIC = b"PK\x03\x04"

ALLOWED_EXTENSIONS = {"pdf", "docx"}


class FileValidationError(Exception):
    """Raised when a file fails validation checks."""
    pass


def validate_uploaded_file(file_path: str, original_filename: str) -> str:
    """
    Validate an uploaded file for processing.

    Checks:
    1. Extension is allowed (pdf or docx)
    2. File size is within configured limit
    3. Magic bytes match the declared extension

    Args:
        file_path: Path where the file was saved.
        original_filename: Original name as uploaded by the user.

    Returns:
        Lowercase file extension without dot (e.g. 'pdf').

    Raises:
        FileValidationError: On any validation failure.
    """
    settings = get_settings()
    path = Path(file_path)

    # 1. Extension check
    extension = path.suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"File type '.{extension}' is not supported. "
            f"Please upload a PDF or DOCX file."
        )

    # 2. Size check
    max_bytes = settings.app.max_file_size_mb * 1024 * 1024
    file_size = path.stat().st_size
    if file_size == 0:
        raise FileValidationError("Uploaded file is empty.")
    if file_size > max_bytes:
        size_mb = file_size / (1024 * 1024)
        raise FileValidationError(
            f"File size {size_mb:.1f} MB exceeds the maximum "
            f"allowed {settings.app.max_file_size_mb} MB."
        )

    # 3. Magic bytes check
    _validate_magic_bytes(path, extension)

    logger.debug(
        "File validation passed",
        extra={
            "file": original_filename,
            "extension": extension,
            "size_kb": round(file_size / 1024, 1),
        },
    )

    return extension


def _validate_magic_bytes(path: Path, extension: str) -> None:
    """
    Read the first few bytes and verify they match the declared type.

    Prevents users from renaming a file and bypassing extension checks.
    """
    with open(path, "rb") as f:
        header = f.read(8)

    if extension == "pdf":
        if not header.startswith(PDF_MAGIC):
            raise FileValidationError(
                "File does not appear to be a valid PDF "
                "(magic bytes mismatch)."
            )
    elif extension == "docx":
        if not header.startswith(DOCX_MAGIC):
            raise FileValidationError(
                "File does not appear to be a valid DOCX "
                "(magic bytes mismatch)."
            )
