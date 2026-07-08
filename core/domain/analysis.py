"""
Analysis Domain Models.

Defines result entities produced by ATS, Skill Gap,
Resume Improvement, and Study Planner services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ATSScoreBreakdown(BaseModel):
    """Detailed breakdown of ATS score components."""

    keyword_match_score: float = Field(ge=0.0, le=100.0)
    skills_match_score: float = Field(ge=0.0, le=100.0)
    experience_match_score: float = Field(ge=0.0, le=100.0)
    education_match_score: float = Field(ge=0.0, le=100.0)


class ATSResult(BaseModel):
    """
    Output of the ATS Scoring Engine.

    Contains the overall match score, keyword analysis,
    and actionable recommendations.
    """

    resume_id: str
    jd_id: str
    overall_score: float = Field(ge=0.0, le=100.0, description="ATS match percentage")
    breakdown: ATSScoreBreakdown
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def score_label(self) -> str:
        """Human-readable score category."""
        if self.overall_score >= 80:
            return "Excellent"
        elif self.overall_score >= 60:
            return "Good"
        elif self.overall_score >= 40:
            return "Fair"
        return "Needs Work"


class SkillGapResult(BaseModel):
    """Output of the Skill Gap Analysis Engine."""

    resume_id: str
    jd_id: str
    missing_technical_skills: list[str] = Field(default_factory=list)
    missing_soft_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    skill_match_percentage: float = Field(ge=0.0, le=100.0)
    learning_recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillLevel(str, Enum):
    """Skill proficiency levels for study planning."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class StudyTopic(BaseModel):
    """A single topic in the study roadmap."""

    topic: str
    skill_level: SkillLevel = SkillLevel.BEGINNER
    estimated_hours: int = Field(ge=1)
    resources: list[str] = Field(default_factory=list)
    week_number: int = Field(ge=1, description="Which week this topic belongs to")


class StudyRoadmap(BaseModel):
    """Output of the Study Planner Service."""

    resume_id: str
    jd_id: str
    total_weeks: int = Field(ge=1)
    topics: list[StudyTopic] = Field(default_factory=list)
    project_recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeImprovement(BaseModel):
    """A single resume improvement suggestion."""

    section: str = Field(description="Resume section this applies to (e.g. 'Summary')")
    issue: str = Field(description="What is wrong or missing")
    suggestion: str = Field(description="Specific actionable improvement")
    priority: str = Field(default="medium", description="high / medium / low")


class ResumeImprovementReport(BaseModel):
    """Output of the Resume Improvement Engine."""

    resume_id: str
    jd_id: Optional[str] = None
    improvements: list[ResumeImprovement] = Field(default_factory=list)
    overall_feedback: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
