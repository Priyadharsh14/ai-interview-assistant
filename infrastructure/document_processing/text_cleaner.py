"""
Text Cleaning Utilities.

Shared text normalisation functions used by all document processors.
Cleans raw extracted text without losing semantic content.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/tabs; preserve paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_control_characters(text: str) -> str:
    """Strip non-printable control characters except newline and tab."""
    cleaned = []
    for char in text:
        category = unicodedata.category(char)
        if char in ("\n", "\t") or category[0] != "C":
            cleaned.append(char)
    return "".join(cleaned)


def normalize_unicode(text: str) -> str:
    """Normalise to NFC and replace typographic punctuation with ASCII."""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2022": "-", "\u2023": "-",
        "\u25cf": "-", "\u25aa": "-",
        "\u25ba": "-", "\u00b7": "-",
        "\u2026": "...", "\u00a0": " ",
    }
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text


def remove_excessive_punctuation(text: str) -> str:
    """Remove lines that consist only of punctuation or separator characters."""
    lines = text.split("\n")
    cleaned = [
        line for line in lines
        if not line.strip() or re.search(r"[a-zA-Z0-9]", line.strip())
    ]
    return "\n".join(cleaned)


def clean_extracted_text(raw_text: str) -> str:
    """
    Full cleaning pipeline: control chars -> unicode -> whitespace -> punctuation lines.

    Args:
        raw_text: Text directly from PDF/DOCX extraction.

    Returns:
        Cleaned text ready for parsing and embedding.
    """
    if not raw_text:
        return ""
    text = remove_control_characters(raw_text)
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    text = remove_excessive_punctuation(text)
    return text


def count_words(text: str) -> int:
    """Count non-empty whitespace-separated tokens."""
    return len(text.split()) if text else 0


def truncate_text(text: str, max_chars: int = 50_000) -> str:
    """
    Truncate text to max_chars at a word boundary.

    Args:
        text: Cleaned text.
        max_chars: Maximum character count.

    Returns:
        Possibly-truncated text with a marker appended.
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "\n\n[... document truncated for processing ...]"
