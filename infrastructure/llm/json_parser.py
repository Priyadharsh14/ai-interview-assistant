"""
LLM JSON Response Parser.

LLMs occasionally wrap JSON in markdown fences or add preamble text.
This module robustly extracts and validates JSON from LLM responses.

Used by all services that expect structured JSON from the LLM.
"""

from __future__ import annotations

import json
import re
from typing import Any

from config.logging_config import get_logger

logger = get_logger(__name__)


class LLMJSONParseError(Exception):
    """Raised when JSON cannot be extracted from an LLM response."""
    pass


def parse_llm_json(raw_response: str) -> Any:
    """
    Extract and parse JSON from an LLM response string.

    Handles common LLM output patterns:
    1. Clean JSON (ideal case)
    2. JSON wrapped in ```json ... ``` markdown fences
    3. JSON wrapped in ``` ... ``` fences
    4. JSON preceded by explanatory text
    5. JSON with trailing explanation after the closing brace/bracket

    Args:
        raw_response: Raw string from LLM completion.

    Returns:
        Parsed Python object (dict or list).

    Raises:
        LLMJSONParseError: If no valid JSON can be extracted.
    """
    if not raw_response or not raw_response.strip():
        raise LLMJSONParseError("LLM returned an empty response")

    text = raw_response.strip()

    # Strategy 1: Direct parse (ideal — LLM followed instructions)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code fences
    fence_patterns = [
        r"```json\s*([\s\S]+?)\s*```",
        r"```\s*([\s\S]+?)\s*```",
    ]
    for pattern in fence_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3: Find the first { or [ and parse from there
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue

        # Find matching closing character
        candidate = _extract_balanced(text, start_idx, start_char, end_char)
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    logger.error(
        "Failed to parse JSON from LLM response",
        extra={"response_preview": text[:200]},
    )
    raise LLMJSONParseError(
        f"Could not extract valid JSON from LLM response. "
        f"Response preview: {text[:200]}"
    )


def _extract_balanced(text: str, start: int, open_c: str, close_c: str) -> str | None:
    """
    Extract a balanced bracket expression starting at `start`.

    Args:
        text: Full text to search in.
        start: Index of the opening bracket.
        open_c: Opening bracket character.
        close_c: Closing bracket character.

    Returns:
        Substring from open to matching close, or None if unbalanced.
    """
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\" and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == open_c:
            depth += 1
        elif char == close_c:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None
