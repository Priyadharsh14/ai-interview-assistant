"""
Mock Interview Service.

Orchestrates a complete mock interview session:
    1. start_session()    — generate questions, create session
    2. submit_answer()    — evaluate one answer, advance question pointer
    3. get_next_question() — return current unanswered question
    4. end_session()      — finalise scores, generate scorecard
    5. get_scorecard()    — retrieve session summary at any point

Session state lives in MockInterviewSession (domain model).
The service is stateless — it operates on the session object
passed in by the caller (Streamlit stores it in session_state).

Design decisions:
    - Stateless service: no internal state between calls.
      The session object IS the state — caller owns it.
    - Lazy model answers: generated on first view of each question
      (not all upfront) to reduce startup latency.
    - Graceful skip: unanswered questions get a 0.0 score in the
      scorecard so sessions can be completed even if the user skips.
    - Scorecard: final report includes per-question scores, category
      averages, an overall band, and targeted improvement suggestions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.logging_config import get_logger
from core.domain.interview import (
    AnswerEvaluation,
    DifficultyLevel,
    InterviewQuestion,
    MockInterviewSession,
    QuestionType,
)
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.services.answer_generator import AnswerGenerator
from core.services.question_generator import QuestionGenerator

logger = get_logger(__name__)


# ------------------------------------------------------------------ #
#  Scorecard domain object                                            #
# ------------------------------------------------------------------ #

@dataclass
class CategoryScore:
    """Average score for one question type."""
    category: str
    average_score: float
    question_count: int
    max_score: float = 10.0


@dataclass
class InterviewScorecard:
    """
    Final summary produced when a mock interview session ends.

    Contains overall performance metrics, per-category breakdowns,
    and targeted improvement recommendations.
    """
    session_id: str
    resume_id: str
    jd_id: str
    overall_score: float           # 0.0–10.0 average across all answers
    overall_band: str              # "Excellent" / "Good" / "Fair" / "Needs Work"
    total_questions: int
    answered_questions: int
    skipped_questions: int
    category_scores: list[CategoryScore] = field(default_factory=list)
    top_strengths: list[str] = field(default_factory=list)
    top_improvements: list[str] = field(default_factory=list)
    duration_minutes: float = 0.0
    completed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def completion_rate(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return round(self.answered_questions / self.total_questions * 100, 1)


# ------------------------------------------------------------------ #
#  Service                                                            #
# ------------------------------------------------------------------ #

class MockInterviewService:
    """
    Manages the lifecycle of a mock interview session.

    Stateless — the MockInterviewSession object is the state.
    The caller (Streamlit session_state) owns and persists the session.

    Usage:
        service = MockInterviewService(
            question_generator=generator,
            answer_generator=evaluator,
        )

        # Start
        session = service.start_session(resume, jd, num_questions=10)

        # Per answer
        question = service.get_next_question(session)
        session = service.submit_answer(session, candidate_answer="...")

        # End
        scorecard = service.end_session(session, resume, jd)
    """

    def __init__(
        self,
        question_generator: QuestionGenerator,
        answer_generator: AnswerGenerator,
    ) -> None:
        self._question_gen = question_generator
        self._answer_gen = answer_generator
        logger.debug("MockInterviewService initialised")

    # ------------------------------------------------------------------ #
    #  Session lifecycle                                                  #
    # ------------------------------------------------------------------ #

    def start_session(
        self,
        resume: Resume,
        jd: JobDescription,
        num_questions: int = 10,
        session_id: Optional[str] = None,
    ) -> MockInterviewSession:
        """
        Create and return a new mock interview session.

        Generates the full question set upfront so the UI can show
        progress (e.g. "Question 3 of 10") from the start.

        Args:
            resume: Candidate's parsed Resume.
            jd: Target JobDescription.
            num_questions: Total questions for this session.
            session_id: Override auto-generated UUID (useful in tests).

        Returns:
            MockInterviewSession ready to use.
        """
        logger.info(
            "Starting mock interview session",
            extra={
                "resume_id": resume.resume_id,
                "jd_id": jd.jd_id,
                "num_questions": num_questions,
            },
        )

        question_set = self._question_gen.generate(
            resume=resume,
            jd=jd,
            num_questions=num_questions,
        )

        session = MockInterviewSession(
            session_id=session_id or str(uuid.uuid4()),
            resume_id=resume.resume_id,
            jd_id=jd.jd_id,
            questions=question_set.questions,
        )

        logger.info(
            "Session created",
            extra={
                "session_id": session.session_id,
                "questions": len(session.questions),
            },
        )
        return session

    def get_next_question(
        self,
        session: MockInterviewSession,
    ) -> Optional[InterviewQuestion]:
        """
        Return the current unanswered question, or None if session is complete.

        Args:
            session: Active MockInterviewSession.

        Returns:
            Next InterviewQuestion, or None when all questions are answered.
        """
        if session.is_complete:
            return None
        if session.current_question_index >= len(session.questions):
            return None
        return session.questions[session.current_question_index]

    def get_model_answer(
        self,
        session: MockInterviewSession,
        question: InterviewQuestion,
        resume: Optional[Resume] = None,
        jd: Optional[JobDescription] = None,
    ) -> str:
        """
        Return the model answer for a question.

        Called when the user requests to see the answer (study mode)
        or after submitting their own answer for comparison.

        If the question already has a model_answer attached (e.g. from
        a previous call), return it directly without an LLM call.

        Args:
            session: Active session (for logging).
            question: The question to answer.
            resume: Optional resume context.
            jd: Optional JD context.

        Returns:
            Model answer string.
        """
        if question.model_answer:
            return question.model_answer

        answer = self._answer_gen.generate_model_answer(question, resume, jd)

        # Cache on the question object to avoid repeated LLM calls
        question.model_answer = answer
        return answer

    def submit_answer(
        self,
        session: MockInterviewSession,
        candidate_answer: str,
        resume: Optional[Resume] = None,
        jd: Optional[JobDescription] = None,
    ) -> tuple[MockInterviewSession, AnswerEvaluation]:
        """
        Evaluate a candidate's answer and advance the session.

        Steps:
        1. Get the current question
        2. Generate model answer (for evaluation reference)
        3. Evaluate the candidate's answer
        4. Record the evaluation in session.evaluations
        5. Advance current_question_index
        6. Mark session complete if all questions answered

        Args:
            session: Active MockInterviewSession (mutated in place).
            candidate_answer: The candidate's answer text.
            resume: Optional resume context for model answer generation.
            jd: Optional JD context for model answer generation.

        Returns:
            Tuple of (updated session, AnswerEvaluation).

        Raises:
            ValueError: If session is already complete or has no questions.
        """
        if session.is_complete:
            raise ValueError(
                f"Session {session.session_id} is already complete."
            )

        current_q = self.get_next_question(session)
        if current_q is None:
            raise ValueError(
                f"Session {session.session_id} has no more questions."
            )

        logger.info(
            "Evaluating answer",
            extra={
                "session_id": session.session_id,
                "question_index": session.current_question_index,
                "question_id": current_q.question_id,
            },
        )

        # Get model answer for evaluation reference
        model_answer = self.get_model_answer(session, current_q, resume, jd)

        # Evaluate the candidate's answer
        evaluation = self._answer_gen.evaluate_answer(
            question=current_q,
            candidate_answer=candidate_answer,
            model_answer=model_answer,
        )

        # Record evaluation and advance
        session.evaluations.append(evaluation)
        session.current_question_index += 1

        # Check if session is now complete
        if session.current_question_index >= len(session.questions):
            session.is_complete = True
            session.completed_at = datetime.utcnow()
            session.final_score = session.average_score
            logger.info(
                "Session completed",
                extra={
                    "session_id": session.session_id,
                    "final_score": session.final_score,
                },
            )

        return session, evaluation

    def skip_question(
        self,
        session: MockInterviewSession,
    ) -> MockInterviewSession:
        """
        Skip the current question without answering.

        Records a 0.0-score evaluation so the scorecard accounts for
        skipped questions rather than ignoring them.

        Args:
            session: Active MockInterviewSession.

        Returns:
            Updated session.
        """
        if session.is_complete:
            return session

        current_q = self.get_next_question(session)
        if current_q is None:
            return session

        skip_evaluation = AnswerEvaluation(
            question_id=current_q.question_id,
            candidate_answer="[SKIPPED]",
            score=0.0,
            strengths=[],
            areas_for_improvement=["Question was skipped."],
            feedback="This question was skipped during the session.",
        )

        session.evaluations.append(skip_evaluation)
        session.current_question_index += 1

        if session.current_question_index >= len(session.questions):
            session.is_complete = True
            session.completed_at = datetime.utcnow()
            session.final_score = session.average_score

        return session

    def end_session(
        self,
        session: MockInterviewSession,
        resume: Optional[Resume] = None,
        jd: Optional[JobDescription] = None,
    ) -> InterviewScorecard:
        """
        Force-complete a session and generate the final scorecard.

        Skips any unanswered questions before computing the scorecard
        so it can be called at any point during a session.

        Args:
            session: MockInterviewSession (may be partially answered).
            resume: Optional for scorecard personalisation.
            jd: Optional for scorecard personalisation.

        Returns:
            InterviewScorecard with complete performance summary.
        """
        # Skip any remaining unanswered questions
        while not session.is_complete:
            session = self.skip_question(session)

        return self._generate_scorecard(session)

    # ------------------------------------------------------------------ #
    #  Scorecard generation                                               #
    # ------------------------------------------------------------------ #

    def _generate_scorecard(
        self,
        session: MockInterviewSession,
    ) -> InterviewScorecard:
        """
        Compile a complete InterviewScorecard from a finished session.

        Computes:
        - Overall score (mean of all evaluations including skips)
        - Per-category averages
        - Top 3 strengths (most common across all evaluations)
        - Top 3 improvement areas (most common across all evaluations)
        - Session duration in minutes
        - Overall performance band
        """
        evaluations = session.evaluations
        questions = session.questions

        # Answered vs skipped
        answered = [e for e in evaluations if e.candidate_answer != "[SKIPPED]"]
        skipped = [e for e in evaluations if e.candidate_answer == "[SKIPPED]"]

        # Overall score
        overall = (
            round(sum(e.score for e in evaluations) / len(evaluations), 2)
            if evaluations else 0.0
        )

        # Category scores
        category_scores = self._compute_category_scores(questions, evaluations)

        # Aggregate strengths and improvements
        all_strengths: list[str] = []
        all_improvements: list[str] = []
        for ev in answered:
            all_strengths.extend(ev.strengths)
            all_improvements.extend(ev.areas_for_improvement)

        # Duration
        duration = 0.0
        if session.completed_at and session.started_at:
            delta = session.completed_at - session.started_at
            duration = round(delta.total_seconds() / 60, 1)

        return InterviewScorecard(
            session_id=session.session_id,
            resume_id=session.resume_id,
            jd_id=session.jd_id,
            overall_score=overall,
            overall_band=self._score_band(overall),
            total_questions=len(questions),
            answered_questions=len(answered),
            skipped_questions=len(skipped),
            category_scores=category_scores,
            top_strengths=self._top_items(all_strengths, 3),
            top_improvements=self._top_items(all_improvements, 3),
            duration_minutes=duration,
        )

    @staticmethod
    def _compute_category_scores(
        questions: list[InterviewQuestion],
        evaluations: list[AnswerEvaluation],
    ) -> list[CategoryScore]:
        """
        Compute average score per question type.

        Maps evaluations back to questions by index position
        (not by question_id) to handle skipped questions cleanly.
        """
        eval_by_qid: dict[str, AnswerEvaluation] = {
            e.question_id: e for e in evaluations
        }

        type_scores: dict[QuestionType, list[float]] = {}
        for q in questions:
            ev = eval_by_qid.get(q.question_id)
            if ev is not None:
                type_scores.setdefault(q.question_type, []).append(ev.score)

        result: list[CategoryScore] = []
        for q_type, scores in type_scores.items():
            avg = round(sum(scores) / len(scores), 2) if scores else 0.0
            result.append(
                CategoryScore(
                    category=q_type.value.replace("_", " ").title(),
                    average_score=avg,
                    question_count=len(scores),
                )
            )

        result.sort(key=lambda c: c.average_score, reverse=True)
        return result

    @staticmethod
    def _score_band(score: float) -> str:
        """Return a human-readable performance band for a 0–10 score."""
        if score >= 8.0:
            return "Excellent"
        elif score >= 6.0:
            return "Good"
        elif score >= 4.0:
            return "Fair"
        return "Needs Work"

    @staticmethod
    def _top_items(items: list[str], n: int) -> list[str]:
        """
        Return the n most commonly occurring items.

        Deduplicates before counting so repeated identical strings
        don't dominate the result.
        """
        if not items:
            return []
        seen: set[str] = set()
        unique: list[str] = []
        for item in items:
            normalised = item.strip().lower()
            if normalised and normalised not in seen:
                seen.add(normalised)
                unique.append(item.strip())
        return unique[:n]
