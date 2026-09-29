"""
Interview Domain Models.

Defines entities for interview questions, answers,
mock interview sessions, and evaluations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Classification of interview question types."""

    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"
    DOMAIN = "domain"
    CULTURE_FIT = "culture_fit"


class DifficultyLevel(str, Enum):
    """Question difficulty tiers."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class InterviewQuestion(BaseModel):
    """A single generated interview question with model answer."""

    question_id: str
    question: str
    question_type: QuestionType
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    topic: str = Field(description="Topic or skill this question tests")
    model_answer: Optional[str] = None
    follow_up_questions: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)


class InterviewQuestionSet(BaseModel):
    """A complete set of interview questions for a resume-JD pair."""

    resume_id: str
    jd_id: str
    questions: list[InterviewQuestion] = Field(default_factory=list)
    total_questions: int = Field(default=0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def model_post_init(self, __context: object) -> None:
        self.total_questions = len(self.questions)


class AnswerEvaluation(BaseModel):
    """Evaluation of a candidate's answer during mock interview."""

    question_id: str
    candidate_answer: str
    score: float = Field(ge=0.0, le=10.0, description="Answer score out of 10")
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    model_answer_summary: str = ""
    feedback: str = ""


class MockInterviewSession(BaseModel):
    """
    A complete mock interview session.

    Tracks questions asked, answers given, and evaluations.
    Supports resuming an in-progress session.
    """

    session_id: str
    resume_id: str
    jd_id: str
    questions: list[InterviewQuestion] = Field(default_factory=list)
    evaluations: list[AnswerEvaluation] = Field(default_factory=list)
    current_question_index: int = Field(default=0)
    is_complete: bool = Field(default=False)
    final_score: Optional[float] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def questions_answered(self) -> int:
        return len(self.evaluations)

    @property
    def questions_remaining(self) -> int:
        return len(self.questions) - self.questions_answered

    @property
    def answered_evaluations(self) -> list[AnswerEvaluation]:
        """Evaluations for questions the candidate actually answered (skips excluded)."""
        return [e for e in self.evaluations if e.candidate_answer != "[SKIPPED]"]

    @property
    def average_score(self) -> float:
        """Mean score over answered questions; skipped questions are not scored as zeros."""
        answered = self.answered_evaluations
        if not answered:
            return 0.0
        return sum(e.score for e in answered) / len(answered)


class ChatMessage(BaseModel):
    """A single message in the RAG chat conversation."""

    role: str = Field(description="'user' or 'assistant'")
    content: str
    sources: list[str] = Field(
        default_factory=list,
        description="Document chunk IDs used as context",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationHistory(BaseModel):
    """Full conversation history for a session."""

    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str, sources: list[str] | None = None) -> None:
        self.messages.append(
            ChatMessage(role=role, content=content, sources=sources or [])
        )
