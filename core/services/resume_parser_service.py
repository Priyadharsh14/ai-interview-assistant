"""
Resume Parser Service.

Takes an ExtractedDocument and uses the LLM to parse it into
a structured Resume domain model.

Pipeline:
    ExtractedDocument (raw text)
    → Build structured prompt
    → Call LLM via BaseLLMProvider
    → Parse JSON response
    → Validate into Resume domain model
    → Return Resume

Design decisions:
- Uses JSON mode prompt engineering (not native JSON mode) for portability
- Falls back to partial Resume on parsing errors — never loses the raw text
- All LLM interaction goes through the provider interface — no direct Groq imports
"""

from __future__ import annotations

import uuid
from datetime import datetime

from config.logging_config import get_logger
from core.domain.resume import (
    ContactInfo,
    DocumentType,
    Education,
    Resume,
    WorkExperience,
)
from core.interfaces.document_processor import ExtractedDocument
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import (
    RESUME_PARSER_SYSTEM,
    resume_parser_user_prompt,
)

logger = get_logger(__name__)


class ResumeParserService:
    """
    Parses raw resume text into a structured Resume domain model.

    Receives a BaseLLMProvider via dependency injection — no Groq imports here.
    This means the service is testable with any mock provider.

    Usage:
        provider = GroqProvider()
        service = ResumeParserService(llm=provider)
        resume = service.parse(extracted_doc)
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        """
        Args:
            llm: Any BaseLLMProvider implementation.
        """
        self._llm = llm
        logger.debug("ResumeParserService initialised")

    def parse(self, document: ExtractedDocument) -> Resume:
        """
        Parse an extracted document into a structured Resume.

        Args:
            document: ExtractedDocument from DocumentProcessingService.

        Returns:
            Resume domain model with all extractable fields populated.
            Raw text is always preserved even if LLM parsing partially fails.
        """
        logger.info(
            "Parsing resume",
            extra={"file": document.file_name, "words": document.word_count},
        )

        resume_id = str(uuid.uuid4())
        document_type = self._detect_document_type(document.file_name)

        # Call LLM for structured extraction
        parsed_data = self._call_llm(document.raw_text)

        # Build Resume from parsed data — gracefully handle missing fields
        resume = self._build_resume(
            resume_id=resume_id,
            document=document,
            document_type=document_type,
            parsed=parsed_data,
        )

        logger.info(
            "Resume parsed successfully",
            extra={
                "resume_id": resume_id,
                "skills_found": len(resume.skills),
                "experience_entries": len(resume.experience),
            },
        )
        return resume

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _call_llm(self, resume_text: str) -> dict:
        """
        Send resume text to LLM and parse the structured response.

        Falls back to an empty dict on parse failure so the service
        can still return a Resume with at least the raw text intact.

        Args:
            resume_text: Cleaned resume text.

        Returns:
            Parsed dict from LLM, or empty dict on failure.
        """
        messages = [
            LLMMessage(role="system", content=RESUME_PARSER_SYSTEM),
            LLMMessage(
                role="user",
                content=resume_parser_user_prompt(resume_text),
            ),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.1,   # Low temperature for deterministic extraction
                max_tokens=4096,
            )
            parsed = parse_llm_json(response.content)
            return parsed if isinstance(parsed, dict) else {}

        except LLMJSONParseError as e:
            logger.warning(
                "LLM JSON parse failed — using fallback empty structure",
                extra={"error": str(e)},
            )
            return {}
        except Exception as e:
            logger.error(
                "LLM call failed during resume parsing",
                extra={"error": str(e)},
            )
            return {}

    def _build_resume(
        self,
        resume_id: str,
        document: ExtractedDocument,
        document_type: DocumentType,
        parsed: dict,
    ) -> Resume:
        """
        Construct a Resume domain model from parsed LLM output.

        All field accesses are guarded — if the LLM omits a field or
        returns an unexpected type, we fall back to a safe default.

        Args:
            resume_id: Generated UUID for this resume.
            document: Original ExtractedDocument.
            document_type: PDF or DOCX.
            parsed: Dict from LLM JSON parsing.

        Returns:
            Validated Resume domain model.
        """
        contact_data = parsed.get("contact") or {}
        contact = ContactInfo(
            name=self._safe_str(contact_data.get("name")),
            email=self._safe_str(contact_data.get("email")),
            phone=self._safe_str(contact_data.get("phone")),
            linkedin=self._safe_str(contact_data.get("linkedin")),
            github=self._safe_str(contact_data.get("github")),
            location=self._safe_str(contact_data.get("location")),
        )

        raw_experience = parsed.get("experience") or []
        experience = [
            WorkExperience(
                company=self._safe_str(exp.get("company")) or "Unknown",
                title=self._safe_str(exp.get("title")) or "Unknown",
                start_date=self._safe_str(exp.get("start_date")),
                end_date=self._safe_str(exp.get("end_date")),
                description=self._safe_str(exp.get("description")) or "",
                technologies=self._safe_list(exp.get("technologies")),
            )
            for exp in raw_experience
            if isinstance(exp, dict)
        ]

        raw_education = parsed.get("education") or []
        education = [
            Education(
                institution=self._safe_str(edu.get("institution")) or "Unknown",
                degree=self._safe_str(edu.get("degree")) or "Unknown",
                field_of_study=self._safe_str(edu.get("field_of_study")),
                graduation_year=self._safe_int(edu.get("graduation_year")),
                gpa=self._safe_float(edu.get("gpa")),
            )
            for edu in raw_education
            if isinstance(edu, dict)
        ]

        return Resume(
            resume_id=resume_id,
            file_name=document.file_name,
            document_type=document_type,
            raw_text=document.raw_text,
            contact=contact,
            summary=self._safe_str(parsed.get("summary")),
            skills=self._safe_list(parsed.get("skills")),
            technical_skills=self._safe_list(parsed.get("technical_skills")),
            soft_skills=self._safe_list(parsed.get("soft_skills")),
            experience=experience,
            education=education,
            certifications=self._safe_list(parsed.get("certifications")),
            projects=self._safe_list(parsed.get("projects")),
        )

    # ------------------------------------------------------------------ #
    #  Type-safe field extractors                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe_str(value: object) -> str | None:
        """Return str or None — never raises."""
        if value is None or value == "":
            return None
        return str(value).strip() or None

    @staticmethod
    def _safe_list(value: object) -> list[str]:
        """Return a list of strings — never raises."""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if item]

    @staticmethod
    def _safe_int(value: object) -> int | None:
        """Return int or None — never raises."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: object) -> float | None:
        """Return float or None — never raises."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _detect_document_type(file_name: str) -> DocumentType:
        """Infer DocumentType from file extension."""
        if file_name.lower().endswith(".pdf"):
            return DocumentType.PDF
        if file_name.lower().endswith(".docx"):
            return DocumentType.DOCX
        return DocumentType.PDF  # Safe default
