"""
Answer Generator Service.

Two responsibilities in one service:
    1. generate_model_answer() — produces a reference answer for an
       InterviewQuestion, used in study mode and as the benchmark
       for mock interview evaluation.

    2. evaluate_answer() — scores a candidate's answer against the
       model answer and returns an AnswerEvaluation with structured
       feedback.

Design decisions:
    - Model answers use question_type-aware prompting:
        technical  → focus on accuracy, depth, examples
        behavioral → enforce STAR format (Situation, Task, Action, Result)
        situational → focus on decision reasoning and trade-offs
    - Evaluation uses a rubric embedded in the prompt so the LLM
      scores against consistent criteria, not arbitrary judgement
    - Both operations fall back gracefully: model answer falls back
      to a structured template; evaluation falls back to neutral scores
    - Temperature 0.4 for answers (creative but grounded)
      Temperature 0.1 for evaluation (deterministic scoring)
"""

from __future__ import annotations

from config.logging_config import get_logger
from core.domain.interview import (
    AnswerEvaluation,
    DifficultyLevel,
    InterviewQuestion,
    QuestionType,
)
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import (
    ANSWER_EVALUATOR_SYSTEM,
    ANSWER_GENERATOR_SYSTEM,
    answer_evaluator_prompt,
    answer_generator_prompt,
)

logger = get_logger(__name__)


# ------------------------------------------------------------------ #
#  Fallback model answers by question type                            #
# ------------------------------------------------------------------ #

_FALLBACK_ANSWERS: dict[QuestionType, str] = {
    QuestionType.TECHNICAL: (
        "A strong technical answer should: (1) define the concept clearly "
        "in your own words, (2) explain how it works with a concrete example, "
        "(3) discuss trade-offs or limitations, and (4) connect it to "
        "production use cases you have encountered."
    ),
    QuestionType.BEHAVIORAL: (
        "Use the STAR method: (S) Describe the Situation briefly — set the "
        "context. (T) State your Task — what were you responsible for? "
        "(A) Walk through your Actions step by step — what did you do and why? "
        "(R) Share the Result — what was the measurable outcome? Be specific "
        "and keep the focus on your individual contribution."
    ),
    QuestionType.SITUATIONAL: (
        "A strong situational answer: (1) identifies the key stakeholders "
        "and constraints, (2) outlines 2–3 options considered, (3) explains "
        "the chosen approach and the reasoning behind it, (4) anticipates "
        "potential risks and mitigations, and (5) describes how success "
        "would be measured."
    ),
    QuestionType.DOMAIN: (
        "A strong domain answer demonstrates: depth of understanding beyond "
        "textbook definitions, real-world application experience, awareness "
        "of alternatives and trade-offs, and up-to-date knowledge of the "
        "field's current best practices."
    ),
    QuestionType.CULTURE_FIT: (
        "Be authentic and specific. Share a concrete example that illustrates "
        "your values in action. Connect your answer to the company's stated "
        "values or the role's requirements. Be concise — 2–3 minutes maximum."
    ),
}


class AnswerGenerator:
    """
    Generates model answers and evaluates candidate responses.

    Both methods share the same LLM provider and prompt infrastructure
    but operate independently — model answer generation does not need
    to happen before evaluation.

    Usage:
        generator = AnswerGenerator(llm=groq_provider)

        # Generate a model answer
        model_answer = generator.generate_model_answer(question, resume, jd)

        # Evaluate a candidate's answer during mock interview
        evaluation = generator.evaluate_answer(
            question=question,
            candidate_answer="My answer here...",
            model_answer=model_answer,
        )
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self._llm = llm
        logger.debug("AnswerGenerator initialised")

    # ------------------------------------------------------------------ #
    #  Model answer generation                                           #
    # ------------------------------------------------------------------ #

    def generate_model_answer(
        self,
        question: InterviewQuestion,
        resume: Resume | None = None,
        jd: JobDescription | None = None,
    ) -> str:
        """
        Generate a model answer for an interview question.

        Adapts the prompt based on question_type:
        - BEHAVIORAL: enforces STAR structure
        - TECHNICAL: focuses on accuracy, depth, and examples
        - SITUATIONAL: focuses on decision framework and trade-offs

        Context (resume + JD) is injected when available so the LLM
        can tailor the answer to the candidate's actual background.

        Args:
            question: The InterviewQuestion to answer.
            resume: Optional Resume for personalised context.
            jd: Optional JobDescription for role-specific context.

        Returns:
            Model answer string. Falls back to a structured template
            on any LLM failure.
        """
        context = self._build_context(resume, jd)

        messages = [
            LLMMessage(role="system", content=ANSWER_GENERATOR_SYSTEM),
            LLMMessage(
                role="user",
                content=answer_generator_prompt(
                    question=question.question,
                    question_type=question.question_type.value,
                    context=context,
                ),
            ),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.4,
                max_tokens=1024,
            )
            parsed = parse_llm_json(response.content)
            answer = str(parsed.get("model_answer") or "").strip()

            if answer:
                logger.debug(
                    "Model answer generated",
                    extra={"question_id": question.question_id},
                )
                return answer

        except LLMJSONParseError:
            # LLM returned prose instead of JSON — use the raw text
            raw = getattr(response, "content", "")
            if raw and len(raw) > 50:
                return raw.strip()
        except Exception as e:
            logger.warning(
                "Model answer generation failed — using fallback",
                extra={"question_id": question.question_id, "error": str(e)},
            )

        return _FALLBACK_ANSWERS.get(
            question.question_type,
            _FALLBACK_ANSWERS[QuestionType.TECHNICAL],
        )

    def generate_batch(
        self,
        questions: list[InterviewQuestion],
        resume: Resume | None = None,
        jd: JobDescription | None = None,
    ) -> dict[str, str]:
        """
        Generate model answers for a list of questions.

        Calls generate_model_answer() per question. In production this
        could be parallelised with asyncio; kept sequential here for
        simplicity and to respect Groq rate limits.

        Args:
            questions: List of InterviewQuestion objects.
            resume: Optional Resume context.
            jd: Optional JobDescription context.

        Returns:
            Dict mapping question_id → model_answer string.
        """
        results: dict[str, str] = {}
        for question in questions:
            results[question.question_id] = self.generate_model_answer(
                question, resume, jd
            )
        return results

    # ------------------------------------------------------------------ #
    #  Answer evaluation                                                  #
    # ------------------------------------------------------------------ #

    def evaluate_answer(
        self,
        question: InterviewQuestion,
        candidate_answer: str,
        model_answer: str = "",
    ) -> AnswerEvaluation:
        """
        Score and provide feedback on a candidate's answer.

        Scoring rubric (embedded in the LLM prompt):
            0–3  : Answer is missing, off-topic, or demonstrates no understanding
            4–5  : Partial answer — touches key points but lacks depth or structure
            6–7  : Good answer — covers main points with reasonable explanation
            8–9  : Strong answer — thorough, structured, with examples
            10   : Exceptional — complete, precise, insightful, well-communicated

        Args:
            question: The question being answered.
            candidate_answer: What the candidate actually said/wrote.
            model_answer: Reference answer (from generate_model_answer).
                          Empty string is acceptable — LLM uses its own knowledge.

        Returns:
            AnswerEvaluation with score, strengths, improvements, feedback.
            Falls back to a neutral evaluation on LLM failure.
        """
        if not candidate_answer or not candidate_answer.strip():
            return self._empty_answer_evaluation(question.question_id)

        messages = [
            LLMMessage(role="system", content=ANSWER_EVALUATOR_SYSTEM),
            LLMMessage(
                role="user",
                content=answer_evaluator_prompt(
                    question=question.question,
                    candidate_answer=candidate_answer,
                    model_answer=model_answer,
                ),
            ),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.1,   # Deterministic scoring
                max_tokens=768,
            )
            parsed = parse_llm_json(response.content)
            return self._build_evaluation(question.question_id, candidate_answer, parsed)

        except LLMJSONParseError as e:
            logger.warning(
                "Answer evaluation JSON parse failed",
                extra={"question_id": question.question_id, "error": str(e)},
            )
        except Exception as e:
            logger.error(
                "Answer evaluation failed",
                extra={"question_id": question.question_id, "error": str(e)},
            )

        return self._fallback_evaluation(question.question_id, candidate_answer)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_context(
        resume: Resume | None,
        jd: JobDescription | None,
    ) -> str:
        """Build a concise context string for the answer generation prompt."""
        parts: list[str] = []

        if resume:
            skills = ", ".join(resume.technical_skills[:8] or resume.skills[:8])
            exp_count = len(resume.experience)
            name = resume.contact.name or "the candidate"
            parts.append(
                f"Candidate: {name}. "
                f"Experience: {exp_count} role(s). "
                f"Key skills: {skills}."
            )

        if jd:
            title = jd.job_title or "the target role"
            required = ", ".join(jd.required_skills[:6])
            parts.append(
                f"Target role: {title}. "
                f"Required skills: {required}."
            )

        return " | ".join(parts) if parts else "General software engineering role."

    @staticmethod
    def _build_evaluation(
        question_id: str,
        candidate_answer: str,
        parsed: dict,
    ) -> AnswerEvaluation:
        """
        Build an AnswerEvaluation from the LLM-parsed response dict.

        Guards every field access against missing or wrong-typed values.
        Score is clamped to [0, 10].
        """
        raw_score = parsed.get("score")
        try:
            score = float(raw_score) if raw_score is not None else 5.0
            score = max(0.0, min(10.0, score))
        except (TypeError, ValueError):
            score = 5.0

        def _safe_list(v: object) -> list[str]:
            if not isinstance(v, list):
                return []
            return [str(x).strip() for x in v if x and str(x).strip()]

        return AnswerEvaluation(
            question_id=question_id,
            candidate_answer=candidate_answer,
            score=score,
            strengths=_safe_list(parsed.get("strengths")),
            areas_for_improvement=_safe_list(parsed.get("areas_for_improvement")),
            model_answer_summary=str(parsed.get("model_answer_summary") or "").strip(),
            feedback=str(parsed.get("feedback") or "").strip(),
        )

    @staticmethod
    def _empty_answer_evaluation(question_id: str) -> AnswerEvaluation:
        """Return a zero-score evaluation for a blank answer."""
        return AnswerEvaluation(
            question_id=question_id,
            candidate_answer="",
            score=0.0,
            strengths=[],
            areas_for_improvement=["Please provide an answer to be evaluated."],
            model_answer_summary="",
            feedback="No answer was provided. Please attempt the question.",
        )

    @staticmethod
    def _fallback_evaluation(
        question_id: str,
        candidate_answer: str,
    ) -> AnswerEvaluation:
        """Return a neutral mid-score evaluation when LLM is unavailable."""
        return AnswerEvaluation(
            question_id=question_id,
            candidate_answer=candidate_answer,
            score=5.0,
            strengths=["Answer received and recorded."],
            areas_for_improvement=[
                "Automated evaluation is temporarily unavailable. "
                "Review the model answer and self-assess."
            ],
            model_answer_summary="",
            feedback=(
                "Evaluation service is temporarily unavailable. "
                "Your answer has been saved. Compare it against the "
                "model answer and the evaluation criteria manually."
            ),
        )
