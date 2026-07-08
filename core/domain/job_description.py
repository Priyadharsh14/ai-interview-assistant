"""
Job Description Domain Model.

Defines the JobDescription entity and related value objects.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ExperienceLevel(str, Enum):
    """Target experience level for the role."""

    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"
    UNKNOWN = "unknown"


class JobDescription(BaseModel):
    """
    Core Job Description domain entity.

    Represents a parsed job description with extracted requirements.
    Created by JDProcessingService after document processing.
    """

    # Identity
    jd_id: str = Field(..., description="Unique identifier for this JD")
    file_name: Optional[str] = Field(None, description="Source file name, if uploaded")

    # Raw content
    raw_text: str = Field(..., description="Full extracted text, unmodified")
    word_count: int = Field(default=0, ge=0)

    # Parsed fields
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.UNKNOWN)
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None

    # Requirements
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_education: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    # Metadata
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_indexed: bool = Field(
        default=False,
        description="True when JD chunks are stored in ChromaDB",
    )

    @field_validator("raw_text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JobDescription raw_text cannot be empty")
        return v

    def model_post_init(self, __context: object) -> None:
        """Compute derived fields after init."""
        if not self.word_count:
            self.word_count = len(self.raw_text.split())

    @property
    def all_required_keywords(self) -> list[str]:
        """Combined list of required skills and keywords for ATS matching."""
        return list(set(self.required_skills + self.keywords))
