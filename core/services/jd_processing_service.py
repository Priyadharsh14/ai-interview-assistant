"""
Job Description Processing Service.

Accepts JD content from two sources:
  1. Plain text paste  (primary — most users copy-paste from job boards)
  2. File upload       (secondary — PDF or DOCX)

Pipeline:
    text / file
    → DocumentProcessingService (for files) or direct text cleaning
    → LLM structured extraction
    → JSON parsing
    → JobDescription domain model

Design decisions:
- Text-paste path skips file I/O entirely for speed
- LLM extraction is identical regardless of input source
- Experience level is normalised from free-text (e.g. "5+ years" → senior)
- Falls back to a minimal JobDescription on LLM failure — never crashes
"""

from __future__ import annotations

import uuid
from typing import Optional

from config.logging_config import get_logger
from core.domain.job_description import ExperienceLevel, JobDescription
from core.interfaces.document_processor import ExtractedDocument
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.document_processing.text_cleaner import clean_extracted_text
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import (
    JD_PARSER_SYSTEM,
    jd_parser_user_prompt,
)

logger = get_logger(__name__)


class JDProcessingService:
    """
    Processes job descriptions into structured JobDescription domain models.

    Handles both plain-text and file-based input through a unified interface.
    All LLM calls go through BaseLLMProvider — no Groq imports here.

    Usage:
        service = JDProcessingService(llm=provider)

        # From pasted text
        jd = service.process_text("Senior Python Engineer required...")

        # From an already-extracted document
        jd = service.process_document(extracted_doc)
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        """
        Args:
            llm: Any BaseLLMProvider implementation.
        """
        self._llm = llm
        logger.debug("JDProcessingService initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def process_text(
        self,
        text: str,
        source_label: str = "pasted_jd",
    ) -> JobDescription:
        """
        Process a pasted or plain-text job description.

        This is the primary path — most users copy-paste JDs from
        LinkedIn, Indeed, or company career pages.

        Args:
            text: Raw job description text.
            source_label: Descriptive label stored as file_name.

        Returns:
            Structured JobDescription domain model.

        Raises:
            ValueError: If text is empty or whitespace-only.
        """
        if not text or not text.strip():
            raise ValueError("Job description text cannot be empty.")

        cleaned = clean_extracted_text(text)
        logger.info(
            "Processing JD from text",
            extra={"source": source_label, "words": len(cleaned.split())},
        )

        return self._parse_and_build(
            raw_text=cleaned,
            file_name=source_label,
            jd_id=str(uuid.uuid4()),
        )

    def process_document(self, document: ExtractedDocument) -> JobDescription:
        """
        Process a JD from an already-extracted document.

        Called when the user uploads a PDF or DOCX job description file.
        The DocumentProcessingService handles extraction before this is called.

        Args:
            document: ExtractedDocument from DocumentProcessingService.

        Returns:
            Structured JobDescription domain model.
        """
        logger.info(
            "Processing JD from document",
            extra={"file": document.file_name, "words": document.word_count},
        )

        return self._parse_and_build(
            raw_text=document.raw_text,
            file_name=document.file_name,
            jd_id=str(uuid.uuid4()),
        )

    # ------------------------------------------------------------------ #
    #  Internal pipeline                                                  #
    # ------------------------------------------------------------------ #

    def _parse_and_build(
        self,
        raw_text: str,
        file_name: Optional[str],
        jd_id: str,
    ) -> JobDescription:
        """
        Run LLM extraction and build the JobDescription model.

        Args:
            raw_text: Cleaned JD text.
            file_name: Source label or filename.
            jd_id: Pre-generated UUID.

        Returns:
            Validated JobDescription domain model.
        """
        parsed = self._call_llm(raw_text)
        jd = self._build_job_description(
            jd_id=jd_id,
            raw_text=raw_text,
            file_name=file_name,
            parsed=parsed,
        )

        logger.info(
            "JD processing complete",
            extra={
                "jd_id": jd_id,
                "job_title": jd.job_title,
                "required_skills": len(jd.required_skills),
                "experience_level": jd.experience_level,
            },
        )
        return jd

    def _call_llm(self, jd_text: str) -> dict:
        """
        Call the LLM to extract structured fields from JD text.

        Falls back to empty dict on any failure so the service always
        returns a usable JobDescription with at least raw_text intact.

        Args:
            jd_text: Cleaned job description text.

        Returns:
            Parsed dict from LLM, or empty dict on failure.
        """
        messages = [
            LLMMessage(role="system", content=JD_PARSER_SYSTEM),
            LLMMessage(role="user", content=jd_parser_user_prompt(jd_text)),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.1,   # Deterministic for structured extraction
                max_tokens=1024,
            )
            return parse_llm_json(response.content)

        except LLMJSONParseError as e:
            logger.warning(
                "LLM JSON parse failed for JD — using fallback",
                extra={"error": str(e)},
            )
            return {}
        except Exception as e:
            logger.error(
                "LLM call failed during JD processing",
                extra={"error": str(e)},
            )
            return {}

    def _build_job_description(
        self,
        jd_id: str,
        raw_text: str,
        file_name: Optional[str],
        parsed: dict,
    ) -> JobDescription:
        """
        Construct a JobDescription domain model from LLM-parsed data.

        All field access is guarded against missing/wrong-typed values.

        Args:
            jd_id: Pre-generated UUID.
            raw_text: Original cleaned text.
            file_name: Source label.
            parsed: Dict from LLM JSON parsing (may be empty on failure).

        Returns:
            Validated JobDescription model.
        """
        experience_level = self._parse_experience_level(
            parsed.get("experience_level")
        )

        return JobDescription(
            jd_id=jd_id,
            file_name=file_name,
            raw_text=raw_text,
            job_title=self._safe_str(parsed.get("job_title")),
            company_name=self._safe_str(parsed.get("company_name")),
            location=self._safe_str(parsed.get("location")),
            experience_level=experience_level,
            experience_years_min=self._safe_int(parsed.get("experience_years_min")),
            experience_years_max=self._safe_int(parsed.get("experience_years_max")),
            required_skills=self._safe_str_list(parsed.get("required_skills")),
            preferred_skills=self._safe_str_list(parsed.get("preferred_skills")),
            required_education=self._safe_str(parsed.get("required_education")),
            responsibilities=self._safe_str_list(parsed.get("responsibilities")),
            keywords=self._safe_str_list(parsed.get("keywords")),
        )

    # ------------------------------------------------------------------ #
    #  Field normalisation helpers                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_experience_level(value: object) -> ExperienceLevel:
        """
        Normalise experience level from LLM output to the enum.

        LLMs sometimes return "Senior Engineer" or "5+ years" instead of
        the exact enum value. This handles the common variants.

        Args:
            value: Raw experience level string from LLM.

        Returns:
            ExperienceLevel enum value, defaulting to UNKNOWN.
        """
        if not value:
            return ExperienceLevel.UNKNOWN

        raw = str(value).lower().strip()

        level_map = {
            "intern": ExperienceLevel.INTERN,
            "internship": ExperienceLevel.INTERN,
            "junior": ExperienceLevel.JUNIOR,
            "entry": ExperienceLevel.JUNIOR,
            "entry-level": ExperienceLevel.JUNIOR,
            "entry level": ExperienceLevel.JUNIOR,
            "mid": ExperienceLevel.MID,
            "mid-level": ExperienceLevel.MID,
            "mid level": ExperienceLevel.MID,
            "intermediate": ExperienceLevel.MID,
            "senior": ExperienceLevel.SENIOR,
            "sr": ExperienceLevel.SENIOR,
            "sr.": ExperienceLevel.SENIOR,
            "lead": ExperienceLevel.LEAD,
            "tech lead": ExperienceLevel.LEAD,
            "staff": ExperienceLevel.LEAD,
            "principal": ExperienceLevel.PRINCIPAL,
            "staff engineer": ExperienceLevel.PRINCIPAL,
            "distinguished": ExperienceLevel.PRINCIPAL,
        }

        if raw in level_map:
            return level_map[raw]

        # Try to match by contained substring (e.g. "senior engineer" → SENIOR)
        for key, level in level_map.items():
            if key in raw:
                return level

        # Fallback: try the enum directly
        try:
            return ExperienceLevel(raw)
        except ValueError:
            return ExperienceLevel.UNKNOWN

    @staticmethod
    def _safe_str(value: object) -> Optional[str]:
        """Return str or None — never raises."""
        if value is None or value == "":
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _safe_str_list(value: object) -> list[str]:
        """Return list of non-empty strings — never raises."""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if item and str(item).strip()]

    @staticmethod
    def _safe_int(value: object) -> Optional[int]:
        """Return int or None — never raises."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
