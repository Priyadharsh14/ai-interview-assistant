"""
Interview Question Generator.

Generates a personalised InterviewQuestionSet from a Resume and
JobDescription using a two-layer strategy.

Layer 1 — Template bank (deterministic):
    A curated bank of question templates per type and topic.
    Instantly produces baseline questions without an LLM call.
    Ensures coverage across technical, behavioural, and situational types
    even when the LLM call fails.

Layer 2 — LLM personalisation:
    Sends resume + JD to Groq/Llama 3.3 for personalised questions.
    Produces questions grounded in the candidate's specific experience
    (e.g. "You mentioned building RAG pipelines at TechCorp...").
    Enriches each question with follow-ups and evaluation criteria.

Merge strategy:
    LLM questions form the primary set (more personalised).
    Template questions fill any gaps to reach the requested count.
    Duplicate questions (same topic + type) are deduplicated.
    Final set is balanced across question types.
"""

from __future__ import annotations

import uuid
from typing import Optional

from config.logging_config import get_logger
from core.domain.interview import (
    DifficultyLevel,
    InterviewQuestion,
    InterviewQuestionSet,
    QuestionType,
)
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import (
    QUESTION_GENERATOR_SYSTEM,
    question_generator_prompt,
)

logger = get_logger(__name__)

# Default question distribution across types
DEFAULT_DISTRIBUTION = {
    QuestionType.TECHNICAL:   5,
    QuestionType.BEHAVIORAL:  3,
    QuestionType.SITUATIONAL: 2,
}

# Template questions by type — used as fallback and gap-fill
_TEMPLATE_BANK: dict[QuestionType, list[dict]] = {
    QuestionType.TECHNICAL: [
        {
            "question": "Walk me through how you would design a RAG pipeline from scratch.",
            "topic": "RAG architecture",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Mentions document ingestion, chunking, embedding, and retrieval",
                "Discusses trade-offs in chunk size and overlap",
                "Addresses context window management",
            ],
        },
        {
            "question": "Explain the difference between fine-tuning and RAG. When would you choose each?",
            "topic": "LLM strategies",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Distinguishes parametric vs non-parametric knowledge",
                "Discusses cost, latency, and update frequency trade-offs",
                "Gives concrete use-case examples for each",
            ],
        },
        {
            "question": "How does cosine similarity work and why is it used in vector search?",
            "topic": "Embeddings and similarity",
            "difficulty": "easy",
            "evaluation_criteria": [
                "Explains the dot product of normalised vectors",
                "Distinguishes from Euclidean distance",
                "Connects to semantic search use-case",
            ],
        },
        {
            "question": "What strategies do you use to prevent hallucination in LLM-powered applications?",
            "topic": "LLM reliability",
            "difficulty": "hard",
            "evaluation_criteria": [
                "Mentions grounding techniques (RAG, citations)",
                "Discusses prompt engineering guardrails",
                "References evaluation and monitoring approaches",
            ],
        },
        {
            "question": "Describe your approach to optimising the latency of an LLM API call.",
            "topic": "Performance optimisation",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Discusses streaming, caching, and batching",
                "Mentions model selection trade-offs",
                "Addresses prompt length management",
            ],
        },
        {
            "question": "How would you implement memory in a multi-turn LLM chatbot?",
            "topic": "Conversation memory",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Distinguishes short-term vs long-term memory",
                "Mentions summarisation and context window limits",
                "Discusses persistent storage options",
            ],
        },
    ],
    QuestionType.BEHAVIORAL: [
        {
            "question": "Tell me about a time you had to quickly learn a new technology to deliver a project.",
            "topic": "Learning agility",
            "difficulty": "easy",
            "evaluation_criteria": [
                "Uses STAR format (Situation, Task, Action, Result)",
                "Describes a concrete technology and timeline",
                "Quantifies the outcome where possible",
            ],
        },
        {
            "question": "Describe a situation where your technical solution failed in production. How did you handle it?",
            "topic": "Resilience and debugging",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Demonstrates ownership and accountability",
                "Describes systematic debugging approach",
                "Explains what changed to prevent recurrence",
            ],
        },
        {
            "question": "Tell me about a time you had to explain a complex technical concept to a non-technical stakeholder.",
            "topic": "Communication",
            "difficulty": "easy",
            "evaluation_criteria": [
                "Demonstrates audience awareness",
                "Uses analogy or visual explanation",
                "Confirms understanding was achieved",
            ],
        },
        {
            "question": "Describe a project where you had to work across teams with different priorities.",
            "topic": "Collaboration",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Shows stakeholder management skills",
                "Describes conflict resolution",
                "Demonstrates outcome focus",
            ],
        },
    ],
    QuestionType.SITUATIONAL: [
        {
            "question": "You're two days before a release and discover a critical bug in the LLM output quality. What do you do?",
            "topic": "Crisis management",
            "difficulty": "hard",
            "evaluation_criteria": [
                "Prioritises impact assessment over immediate fixes",
                "Involves appropriate stakeholders",
                "Considers rollback vs hotfix options",
            ],
        },
        {
            "question": "Your manager asks you to ship a feature that uses an LLM in a way you believe is unsafe. How do you respond?",
            "topic": "AI ethics and communication",
            "difficulty": "medium",
            "evaluation_criteria": [
                "Raises concern clearly and professionally",
                "Offers alternative solutions",
                "Demonstrates understanding of AI safety",
            ],
        },
        {
            "question": "You join a team that has a working ML system but no tests and no documentation. What's your first month plan?",
            "topic": "Technical leadership",
            "difficulty": "hard",
            "evaluation_criteria": [
                "Prioritises understanding before changing",
                "Plans incrementally — tests before refactoring",
                "Considers team buy-in and communication",
            ],
        },
    ],
}


class QuestionGenerator:
    """
    Generates a personalised interview question set.

    Balances LLM-personalised questions with template fallbacks
    to ensure reliable delivery even when the LLM is unavailable.

    Usage:
        generator = QuestionGenerator(llm=groq_provider)
        question_set = generator.generate(
            resume=resume,
            jd=job_description,
            num_questions=10,
        )
        for q in question_set.questions:
            print(f"[{q.question_type}] {q.question}")
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self._llm = llm
        logger.debug("QuestionGenerator initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def generate(
        self,
        resume: Resume,
        jd: JobDescription,
        num_questions: int = 10,
        distribution: Optional[dict[QuestionType, int]] = None,
    ) -> InterviewQuestionSet:
        """
        Generate a personalised interview question set.

        Args:
            resume: Parsed Resume domain model.
            jd: Parsed JobDescription domain model.
            num_questions: Total questions to generate (default 10).
            distribution: Override the default type distribution.
                          e.g. {QuestionType.TECHNICAL: 7, QuestionType.BEHAVIORAL: 3}

        Returns:
            InterviewQuestionSet with questions ordered by type then difficulty.
        """
        logger.info(
            "Generating interview questions",
            extra={
                "resume_id": resume.resume_id,
                "jd_id": jd.jd_id,
                "num_questions": num_questions,
            },
        )

        # Resolve effective distribution
        effective_dist = self._resolve_distribution(
            distribution or DEFAULT_DISTRIBUTION, num_questions
        )

        # Layer 2: LLM personalised questions
        llm_questions = self._llm_generate(resume, jd, num_questions)

        # Layer 1: Template questions for gap-fill
        template_questions = self._template_generate(effective_dist)

        # Merge and finalise
        questions = self._merge_and_finalise(
            llm_questions, template_questions, num_questions, effective_dist
        )

        question_set = InterviewQuestionSet(
            resume_id=resume.resume_id,
            jd_id=jd.jd_id,
            questions=questions,
        )

        logger.info(
            "Question generation complete",
            extra={
                "resume_id": resume.resume_id,
                "total": question_set.total_questions,
            },
        )
        return question_set

    def generate_by_topic(
        self,
        resume: Resume,
        jd: JobDescription,
        topic: str,
        num_questions: int = 5,
    ) -> list[InterviewQuestion]:
        """
        Generate questions focused on a specific topic or skill.

        Useful for the study planner — generates targeted practice
        questions for a single skill gap (e.g. "LangChain").

        Args:
            resume: Parsed Resume.
            jd: Parsed JD.
            topic: Skill or topic to focus on (e.g. "ChromaDB", "System Design").
            num_questions: Number of questions to generate.

        Returns:
            List of InterviewQuestion focused on the topic.
        """
        # Build a focused prompt by injecting the topic
        focused_jd = jd.model_copy(
            update={"raw_text": f"Focus area: {topic}\n\n" + jd.raw_text}
        )
        question_set = self.generate(focused_jd if False else resume, focused_jd, num_questions)
        return question_set.questions[:num_questions]

    # ------------------------------------------------------------------ #
    #  Layer 2: LLM generation                                           #
    # ------------------------------------------------------------------ #

    def _llm_generate(
        self,
        resume: Resume,
        jd: JobDescription,
        num_questions: int,
    ) -> list[InterviewQuestion]:
        """
        Call the LLM to generate personalised questions.

        Falls back to empty list on any failure — template questions
        always fill the gap.
        """
        messages = [
            LLMMessage(role="system", content=QUESTION_GENERATOR_SYSTEM),
            LLMMessage(
                role="user",
                content=question_generator_prompt(
                    resume.raw_text, jd.raw_text, num_questions
                ),
            ),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.6,    # Moderate creativity for varied questions
                max_tokens=2048,
            )
            raw = parse_llm_json(response.content)
            return self._parse_llm_questions(raw)
        except LLMJSONParseError as e:
            logger.warning("LLM question JSON parse failed", extra={"error": str(e)})
            return []
        except Exception as e:
            logger.error("LLM question generation failed", extra={"error": str(e)})
            return []

    # ------------------------------------------------------------------ #
    #  Layer 1: Template generation                                       #
    # ------------------------------------------------------------------ #

    def _template_generate(
        self,
        distribution: dict[QuestionType, int],
    ) -> list[InterviewQuestion]:
        """
        Draw questions from the template bank to fill type quotas.

        Questions are drawn in order (no shuffling) so output is
        deterministic and reproducible in tests.
        """
        questions: list[InterviewQuestion] = []

        for q_type, count in distribution.items():
            templates = _TEMPLATE_BANK.get(q_type, [])
            for template in templates[:count]:
                questions.append(
                    InterviewQuestion(
                        question_id=f"tmpl_{str(uuid.uuid4())[:8]}",
                        question=template["question"],
                        question_type=q_type,
                        difficulty=self._parse_difficulty(template.get("difficulty")),
                        topic=template.get("topic", q_type.value),
                        evaluation_criteria=template.get("evaluation_criteria", []),
                        follow_up_questions=[],
                    )
                )

        return questions

    # ------------------------------------------------------------------ #
    #  Merge and finalise                                                 #
    # ------------------------------------------------------------------ #

    def _merge_and_finalise(
        self,
        llm_questions: list[InterviewQuestion],
        template_questions: list[InterviewQuestion],
        target_count: int,
        distribution: dict[QuestionType, int],
    ) -> list[InterviewQuestion]:
        """
        Merge LLM and template questions into a final balanced set.

        Strategy:
        1. Use LLM questions as primary (personalised)
        2. Fill gaps per type using templates
        3. Deduplicate by (type, topic) normalised key
        4. Sort: technical → behavioural → situational, then easy → hard

        Args:
            llm_questions: Personalised questions from LLM.
            template_questions: Fallback questions from template bank.
            target_count: Desired total.
            distribution: Type quota dict.

        Returns:
            Finalised, ordered question list capped at target_count.
        """
        seen_keys: set[str] = set()
        final: list[InterviewQuestion] = []

        def _add(q: InterviewQuestion) -> bool:
            key = f"{q.question_type.value}|{q.topic.lower()[:30]}"
            if key not in seen_keys:
                seen_keys.add(key)
                final.append(q)
                return True
            return False

        # LLM questions first (preferred)
        for q in llm_questions:
            _add(q)

        # Templates fill remaining quota per type
        type_counts: dict[QuestionType, int] = {}
        for q in final:
            type_counts[q.question_type] = type_counts.get(q.question_type, 0) + 1

        for q in template_questions:
            if len(final) >= target_count:
                break
            quota = distribution.get(q.question_type, 0)
            current = type_counts.get(q.question_type, 0)
            if current < quota:
                if _add(q):
                    type_counts[q.question_type] = current + 1

        # Sort: type order then difficulty
        type_order = {
            QuestionType.TECHNICAL: 0,
            QuestionType.DOMAIN: 1,
            QuestionType.BEHAVIORAL: 2,
            QuestionType.SITUATIONAL: 3,
            QuestionType.CULTURE_FIT: 4,
        }
        diff_order = {
            DifficultyLevel.EASY: 0,
            DifficultyLevel.MEDIUM: 1,
            DifficultyLevel.HARD: 2,
        }
        final.sort(key=lambda q: (
            type_order.get(q.question_type, 5),
            diff_order.get(q.difficulty, 1),
        ))

        return final[:target_count]

    # ------------------------------------------------------------------ #
    #  Parsers and helpers                                                #
    # ------------------------------------------------------------------ #

    def _parse_llm_questions(self, raw: object) -> list[InterviewQuestion]:
        """
        Parse LLM JSON array into InterviewQuestion objects.

        Silently skips malformed entries. Assigns UUID question IDs.
        """
        if not isinstance(raw, list):
            return []

        questions: list[InterviewQuestion] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            try:
                question_text = str(item.get("question") or "").strip()
                if not question_text:
                    continue

                q = InterviewQuestion(
                    question_id=str(item.get("question_id") or f"llm_{i}_{str(uuid.uuid4())[:8]}"),
                    question=question_text,
                    question_type=self._parse_question_type(
                        item.get("question_type")
                    ),
                    difficulty=self._parse_difficulty(item.get("difficulty")),
                    topic=str(item.get("topic") or "General").strip(),
                    evaluation_criteria=self._safe_str_list(
                        item.get("evaluation_criteria")
                    ),
                    follow_up_questions=self._safe_str_list(
                        item.get("follow_up_questions")
                    ),
                )
                questions.append(q)
            except Exception as e:
                logger.debug("Skipping malformed LLM question", extra={"error": str(e)})
                continue

        return questions

    @staticmethod
    def _parse_question_type(value: object) -> QuestionType:
        """Normalise LLM question_type string to QuestionType enum."""
        if not value:
            return QuestionType.TECHNICAL
        raw = str(value).lower().strip()
        mapping = {
            "technical": QuestionType.TECHNICAL,
            "behavioral": QuestionType.BEHAVIORAL,
            "behavioural": QuestionType.BEHAVIORAL,
            "situational": QuestionType.SITUATIONAL,
            "domain": QuestionType.DOMAIN,
            "culture_fit": QuestionType.CULTURE_FIT,
            "culture fit": QuestionType.CULTURE_FIT,
        }
        return mapping.get(raw, QuestionType.TECHNICAL)

    @staticmethod
    def _parse_difficulty(value: object) -> DifficultyLevel:
        """Normalise LLM difficulty string to DifficultyLevel enum."""
        if not value:
            return DifficultyLevel.MEDIUM
        raw = str(value).lower().strip()
        mapping = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MEDIUM,
            "hard": DifficultyLevel.HARD,
            "difficult": DifficultyLevel.HARD,
        }
        return mapping.get(raw, DifficultyLevel.MEDIUM)

    @staticmethod
    def _resolve_distribution(
        distribution: dict[QuestionType, int],
        target: int,
    ) -> dict[QuestionType, int]:
        """
        Scale a type distribution to match the target question count.

        If the distribution total doesn't match target, scale each type
        proportionally and allocate remainder to TECHNICAL (highest priority).
        """
        total = sum(distribution.values())
        if total == 0:
            return {QuestionType.TECHNICAL: target}
        if total == target:
            return distribution

        # Scale proportionally
        scaled: dict[QuestionType, int] = {}
        allocated = 0
        types = list(distribution.keys())

        for i, q_type in enumerate(types):
            if i == len(types) - 1:
                # Last type gets the remainder
                scaled[q_type] = target - allocated
            else:
                count = round(distribution[q_type] / total * target)
                scaled[q_type] = max(0, count)
                allocated += scaled[q_type]

        return scaled

    @staticmethod
    def _safe_str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if v and str(v).strip()]
