"""
Skill Gap Analysis Engine.

Identifies the delta between what a candidate has and what a job requires.

Two-layer strategy (mirrors ATSEngine):
    Layer 1 — Deterministic set-difference:
        Exact skill matching using normalised string comparison.
        Fast, reproducible, no LLM required.
        Produces matched/missing skill lists and a match percentage.

    Layer 2 — LLM-enhanced:
        Sends resume + JD to the LLM for contextual gap analysis.
        Handles synonyms ("ML" = "Machine Learning"), implied skills
        ("FastAPI experience" implies "REST API" knowledge), and
        soft skill inference from job responsibilities text.
        Generates specific, prioritised learning recommendations.

Merge strategy:
    - Deterministic results form the foundation (precise, verifiable)
    - LLM supplements with synonym-aware matches and additional gaps
    - Recommendations always come from LLM when available (richer prose)
    - Skill match percentage is a weighted blend of both layers
"""

from __future__ import annotations

import re
from typing import Optional

from config.logging_config import get_logger
from core.domain.analysis import SkillGapResult
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import SKILL_GAP_SYSTEM, skill_gap_prompt

logger = get_logger(__name__)

# Curated list of recognised soft skills for deterministic classification
KNOWN_SOFT_SKILLS: frozenset[str] = frozenset({
    "communication", "leadership", "teamwork", "collaboration",
    "problem solving", "problem-solving", "critical thinking",
    "time management", "adaptability", "creativity", "mentoring",
    "presentation", "negotiation", "project management",
    "attention to detail", "analytical", "organisational",
    "organizational", "interpersonal", "written communication",
    "verbal communication", "conflict resolution", "decision making",
    "stakeholder management", "agile", "scrum",
})


class SkillGapEngine:
    """
    Analyses the skill gap between a candidate's resume and a job description.

    Returns a SkillGapResult with:
    - missing_technical_skills: hard technical skills the candidate lacks
    - missing_soft_skills: interpersonal/process skills the candidate lacks
    - matched_skills: skills present in both resume and JD
    - skill_match_percentage: 0–100 score of overall skill coverage
    - learning_recommendations: specific actions to close each gap

    Usage:
        engine = SkillGapEngine(llm=groq_provider)
        result = engine.analyse(resume, job_description)
        print(f"Missing skills: {result.missing_technical_skills}")
        print(f"Match: {result.skill_match_percentage:.1f}%")
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self._llm = llm
        logger.debug("SkillGapEngine initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def analyse(self, resume: Resume, jd: JobDescription) -> SkillGapResult:
        """
        Perform full skill gap analysis.

        Args:
            resume: Parsed Resume domain model.
            jd: Parsed JobDescription domain model.

        Returns:
            SkillGapResult with gaps, matches, percentage, and recommendations.
        """
        logger.info(
            "Analysing skill gap",
            extra={"resume_id": resume.resume_id, "jd_id": jd.jd_id},
        )

        # Layer 1: deterministic set-difference analysis
        det = self._deterministic_analysis(resume, jd)

        # Layer 2: LLM-enhanced analysis
        llm_data = self._llm_analysis(resume, jd)

        # Merge into final result
        result = self._build_result(resume, jd, det, llm_data)

        logger.info(
            "Skill gap analysis complete",
            extra={
                "resume_id": resume.resume_id,
                "missing_technical": len(result.missing_technical_skills),
                "missing_soft": len(result.missing_soft_skills),
                "match_pct": result.skill_match_percentage,
            },
        )
        return result

    # ------------------------------------------------------------------ #
    #  Layer 1: Deterministic                                             #
    # ------------------------------------------------------------------ #

    def _deterministic_analysis(self, resume: Resume, jd: JobDescription) -> dict:
        """
        Compute skill gaps using exact normalised string matching.

        Normalises both sides to lowercase stripped strings, then
        computes set difference. Classifies each gap as technical or soft
        using the KNOWN_SOFT_SKILLS lookup table.

        Returns:
            Dict with matched, missing_technical, missing_soft, match_pct.
        """
        # Build resume skill set from all skill fields
        resume_skills_norm: set[str] = {
            self._normalise(s)
            for s in (resume.skills + resume.technical_skills + resume.soft_skills)
            if s
        }

        # Also scan raw_text for skills mentioned inline
        resume_text_lower = resume.raw_text.lower()

        # Build JD required skill set
        jd_required_norm: dict[str, str] = {
            self._normalise(s): s   # norm → original
            for s in jd.required_skills
            if s
        }
        jd_preferred_norm: dict[str, str] = {
            self._normalise(s): s
            for s in jd.preferred_skills
            if s
        }

        all_jd_norm = {**jd_required_norm, **jd_preferred_norm}

        if not all_jd_norm:
            return {
                "matched": [],
                "missing_technical": [],
                "missing_soft": [],
                "match_pct": 0.0,
            }

        matched_originals: list[str] = []
        missing_technical: list[str] = []
        missing_soft: list[str] = []

        for norm_skill, original_skill in all_jd_norm.items():
            # Check resume skill sets first, then scan raw text
            in_resume = (
                norm_skill in resume_skills_norm
                or norm_skill in resume_text_lower
            )

            if in_resume:
                matched_originals.append(original_skill)
            else:
                if self._is_soft_skill(norm_skill):
                    missing_soft.append(original_skill)
                else:
                    missing_technical.append(original_skill)

        total = len(all_jd_norm)
        match_pct = round(len(matched_originals) / total * 100, 1)

        return {
            "matched": matched_originals,
            "missing_technical": missing_technical,
            "missing_soft": missing_soft,
            "match_pct": match_pct,
        }

    # ------------------------------------------------------------------ #
    #  Layer 2: LLM-enhanced                                              #
    # ------------------------------------------------------------------ #

    def _llm_analysis(self, resume: Resume, jd: JobDescription) -> dict:
        """
        Call LLM for synonym-aware, contextual skill gap analysis.

        Handles cases that string matching misses:
        - Synonyms: "ML" ↔ "Machine Learning"
        - Implied skills: "built REST APIs" implies "API design"
        - Soft skills inferred from responsibility descriptions

        Falls back to empty dict on any failure.
        """
        messages = [
            LLMMessage(role="system", content=SKILL_GAP_SYSTEM),
            LLMMessage(
                role="user",
                content=skill_gap_prompt(resume.raw_text, jd.raw_text),
            ),
        ]

        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            return parse_llm_json(response.content)
        except LLMJSONParseError as e:
            logger.warning("LLM skill gap JSON parse failed", extra={"error": str(e)})
            return {}
        except Exception as e:
            logger.error("LLM skill gap call failed", extra={"error": str(e)})
            return {}

    # ------------------------------------------------------------------ #
    #  Result assembly                                                    #
    # ------------------------------------------------------------------ #

    def _build_result(
        self,
        resume: Resume,
        jd: JobDescription,
        det: dict,
        llm: dict,
    ) -> SkillGapResult:
        """
        Merge deterministic and LLM analyses into a final SkillGapResult.

        Merge strategy:
        - Matched skills: union of deterministic + LLM matched lists
        - Missing technical: deterministic base, deduplicated against LLM extras
        - Missing soft: deterministic base, deduplicated against LLM extras
        - Skill match %: if LLM provides one, blend 70% det / 30% LLM
        - Recommendations: LLM if available (richer), else generated fallback

        Args:
            resume: Source resume.
            jd: Source JD.
            det: Deterministic analysis dict.
            llm: LLM analysis dict (may be empty).

        Returns:
            Validated SkillGapResult.
        """
        # Matched skills — merge and deduplicate
        matched = self._merge_unique(
            det["matched"],
            self._safe_str_list(llm.get("matched_skills")),
        )

        # Missing technical skills — deterministic base + LLM extras
        missing_tech = self._merge_unique(
            det["missing_technical"],
            self._safe_str_list(llm.get("missing_technical_skills")),
        )
        # Missing soft skills
        missing_soft = self._merge_unique(
            det["missing_soft"],
            self._safe_str_list(llm.get("missing_soft_skills")),
        )

        # A skill can't be both matched and missing. The two analyses word
        # skills differently ("OOP" vs "Object-Oriented Programming (OOP)"),
        # so compare on canonical form against the merged matched list.
        matched_canon = [self._canon(s) for s in matched]
        missing_tech = [s for s in missing_tech if not self._is_covered(s, matched_canon)]
        missing_soft = [s for s in missing_soft if not self._is_covered(s, matched_canon)]

        # Skill match percentage — blend if LLM provides a value
        llm_pct = self._safe_float(llm.get("skill_match_percentage"))
        if llm_pct is not None:
            match_pct = round(0.7 * det["match_pct"] + 0.3 * llm_pct, 1)
        else:
            match_pct = det["match_pct"]

        match_pct = max(0.0, min(100.0, match_pct))

        # Learning recommendations
        recommendations = self._safe_str_list(llm.get("learning_recommendations"))
        if not recommendations:
            recommendations = self._generate_fallback_recommendations(
                missing_technical=missing_tech,
                missing_soft=missing_soft,
            )

        return SkillGapResult(
            resume_id=resume.resume_id,
            jd_id=jd.jd_id,
            missing_technical_skills=missing_tech,
            missing_soft_skills=missing_soft,
            matched_skills=matched,
            skill_match_percentage=match_pct,
            learning_recommendations=recommendations,
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalise(skill: str) -> str:
        """
        Normalise a skill string for comparison.

        Lowercases, strips whitespace, removes trailing punctuation.
        Keeps hyphens (e.g. "problem-solving").
        """
        return skill.lower().strip().rstrip(".,;:")

    @staticmethod
    def _canon(skill: str) -> str:
        """Canonical form for fuzzy skill comparison: drop parentheticals and punctuation."""
        text = re.sub(r"\([^)]*\)", " ", skill.lower())
        return " ".join(re.sub(r"[^a-z0-9+#]+", " ", text).split())

    @classmethod
    def _is_covered(cls, skill: str, matched_canon: list[str]) -> bool:
        """
        True if `skill` equals, or is a multi-word phrase contained in
        (or containing a multi-word phrase of), an already-matched skill.
        """
        c = cls._canon(skill)
        if not c:
            return False
        padded = f" {c} "
        for m in matched_canon:
            if not m:
                continue
            if c == m:
                return True
            if len(m.split()) >= 2 and f" {m} " in padded:
                return True
            if len(c.split()) >= 2 and padded.strip() and f" {c} " in f" {m} ":
                return True
        return False

    @staticmethod
    def _is_soft_skill(normalised_skill: str) -> bool:
        """
        Return True if a skill is a soft/interpersonal skill.

        Checks against KNOWN_SOFT_SKILLS lookup table, then falls back
        to keyword detection for unlisted soft skills.
        """
        if normalised_skill in KNOWN_SOFT_SKILLS:
            return True

        soft_indicators = [
            "communicat", "collaborat", "leadership", "management",
            "interpersonal", "teamwork", "presentation", "organisation",
            "mentoring", "coaching",
        ]
        return any(ind in normalised_skill for ind in soft_indicators)

    @staticmethod
    def _merge_unique(base: list[str], extras: list[str]) -> list[str]:
        """
        Merge two lists, deduplicating by lowercase value.

        Base list items are always included first (preserves ordering).
        Extras are appended only if not already present.
        """
        seen: set[str] = set()
        result: list[str] = []
        for item in base + extras:
            key = item.lower().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def _safe_str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if v and str(v).strip()]

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            f = float(value)
            return f if 0.0 <= f <= 100.0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _generate_fallback_recommendations(
        missing_technical: list[str],
        missing_soft: list[str],
    ) -> list[str]:
        """
        Generate basic learning recommendations when the LLM is unavailable.
        """
        recs: list[str] = []

        for skill in missing_technical[:4]:
            recs.append(
                f"Learn {skill}: search for official documentation, "
                f"a hands-on Udemy course, or a free YouTube tutorial series."
            )

        for skill in missing_soft[:2]:
            recs.append(
                f"Develop {skill}: consider a workshop, online course, "
                f"or targeted practice in your current role."
            )

        if not recs:
            recs.append(
                "Your skills closely match the job requirements. "
                "Focus on deepening expertise and building portfolio projects."
            )

        return recs
