"""
Resume Domain Model.

Defines the core Resume entity and all related value objects.
These are plain Pydantic models — no framework dependencies.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    """Supported document types."""

    PDF = "pdf"
    DOCX = "docx"


class ContactInfo(BaseModel):
    """Candidate contact information extracted from resume."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: Optional[str] = None


class WorkExperience(BaseModel):
    """A single work experience entry."""

    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class Education(BaseModel):
    """A single education entry."""

    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None


class Resume(BaseModel):
    """
    Core Resume domain entity.

    Represents a fully parsed resume with all extracted sections.
    Created by ResumeParserService after document processing.
    """

    # Identity
    resume_id: str = Field(..., description="Unique identifier for this resume")
    file_name: str = Field(..., description="Original uploaded file name")
    document_type: DocumentType = Field(..., description="PDF or DOCX")

    # Raw content
    raw_text: str = Field(..., description="Full extracted text, unmodified")
    word_count: int = Field(default=0, ge=0)

    # Parsed sections
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)

    # Metadata
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_indexed: bool = Field(
        default=False,
        description="True when resume chunks are stored in ChromaDB",
    )

    @field_validator("raw_text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Resume raw_text cannot be empty")
        return v

    def model_post_init(self, __context: object) -> None:
        """Compute derived fields after init."""
        if not self.word_count:
            self.word_count = len(self.raw_text.split())
