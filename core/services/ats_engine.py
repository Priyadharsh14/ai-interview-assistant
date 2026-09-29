"""
ATS (Applicant Tracking System) Scoring Engine.

Compares a Resume against a JobDescription and produces a structured
ATSResult with an overall match score, component breakdown, matched/missing
keywords, and prioritised recommendations.

Two-layer scoring strategy:
    Layer 1 — Deterministic (fast, no LLM):
        Keyword matching via normalised string comparison.
        Skills intersection between resume skills and JD required skills.
        Produces a baseline score before touching the LLM.

    Layer 2 — LLM-enhanced (deep analysis):
        Sends resume + JD to Groq/Llama 3.3 for holistic scoring.
        LLM adds experience alignment, education fit, and writing quality.
        Merges with Layer 1 results for the final ATSResult.

Why two layers?
    The deterministic layer is cheap and runs offline (useful for batch
    processing and testing). The LLM layer adds context-aware judgement
    that pure string matching cannot — e.g. "5 years Python" in a resume
    matching "senior Python engineer" in a JD.
    Together they produce richer, more actionable output.
"""

from __future__ import annotations

import re
from typing import Optional

from config.logging_config import get_logger
from core.domain.analysis import ATSResult, ATSScoreBreakdown
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import ATS_SYSTEM, ats_scoring_prompt

logger = get_logger(__name__)

# Weights for the overall score components
SCORE_WEIGHTS = {
    "keyword_match":    0.35,
    "skills_match":     0.35,
    "experience_match": 0.20,
    "education_match":  0.10,
}


class ATSEngine:
    """
    Scores a resume against a job description using hybrid analysis.

    Combines fast deterministic keyword matching with LLM-based
    contextual scoring to produce a comprehensive ATSResult.

    Usage:
        engine = ATSEngine(llm=groq_provider)
        result = engine.score(resume, job_description)
        print(f"ATS Score: {result.overall_score:.1f}% ({result.score_label})")
        print(f"Missing keywords: {result.missing_keywords}")
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        """
        Args:
            llm: Any BaseLLMProvider implementation.
        """
        self._llm = llm
        logger.debug("ATSEngine initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def score(self, resume: Resume, jd: JobDescription) -> ATSResult:
        """
        Score a resume against a job description.

        Runs deterministic keyword analysis first, then calls the LLM
        for contextual scoring. LLM failure falls back gracefully to the
        deterministic scores only.

        Args:
            resume: Parsed Resume domain model.
            jd: Parsed JobDescription domain model.

        Returns:
            ATSResult with overall score, breakdown, and recommendations.
        """
        logger.info(
            "Scoring resume against JD",
            extra={
                "resume_id": resume.resume_id,
                "jd_id": jd.jd_id,
                "job_title": jd.job_title,
            },
        )

        # Layer 1: Deterministic analysis
        det = self._deterministic_analysis(resume, jd)

        # Layer 2: LLM-enhanced scoring
        llm_data = self._llm_analysis(resume, jd)

        # Merge both layers into a final ATSResult
        result = self._build_result(resume, jd, det, llm_data)

        logger.info(
            "ATS scoring complete",
            extra={
                "resume_id": resume.resume_id,
                "score": result.overall_score,
                "label": result.score_label,
                "missing_keywords": len(result.missing_keywords),
            },
        )
        return result

    # ------------------------------------------------------------------ #
    #  Layer 1: Deterministic keyword analysis                           #
    # ------------------------------------------------------------------ #

    def _deterministic_analysis(
        self,
        resume: Resume,
        jd: JobDescription,
    ) -> dict:
        """
        Fast, offline keyword and skill matching.

        Normalises all tokens to lowercase and strips punctuation before
        comparing so "Python," matches "Python" and "langchain" matches
        "LangChain".

        Returns:
            Dict with matched_keywords, missing_keywords, keyword_score,
            skills_score computed without any LLM call.
        """
        # Tokenise resume text for broad keyword search
        resume_tokens = self._tokenize(resume.raw_text)
        resume_skills_lower = {s.lower() for s in resume.skills + resume.technical_skills}

        # JD keywords and required skills
        jd_keywords = set(jd.all_required_keywords)
        jd_skills = {s.lower() for s in jd.required_skills}

        # Keyword matching — check if each JD keyword appears anywhere in the resume
        matched_kw: list[str] = []
        missing_kw: list[str] = []
        for kw in jd_keywords:
            kw_tokens = self._tokenize(kw)
            # All tokens of the keyword must appear in the resume
            if kw_tokens and kw_tokens.issubset(resume_tokens):
                matched_kw.append(kw)
            else:
                missing_kw.append(kw)

        keyword_score = (
            len(matched_kw) / len(jd_keywords) * 100
            if jd_keywords else 0.0
        )

        # Skills matching — compare resume skills against JD required skills
        matched_skills = resume_skills_lower & jd_skills
        skills_score = (
            len(matched_skills) / len(jd_skills) * 100
            if jd_skills else keyword_score   # Fall back to keyword score if no skills extracted
        )

        return {
            "matched_keywords": matched_kw,
            "missing_keywords": missing_kw,
            "matched_skills": list(matched_skills),
            "keyword_score": round(keyword_score, 1),
            "skills_score": round(skills_score, 1),
        }

    # ------------------------------------------------------------------ #
    #  Layer 2: LLM-enhanced scoring                                     #
    # ------------------------------------------------------------------ #

    def _llm_analysis(self, resume: Resume, jd: JobDescription) -> dict:
        """
        Call the LLM for contextual ATS analysis.

        Extracts experience alignment, education match, holistic scoring,
        and actionable recommendations that string matching cannot provide.

        Falls back to empty dict on any failure — Layer 1 still runs.

        Returns:
            Parsed dict from LLM, or empty dict on failure.
        """
        messages = [
            LLMMessage(role="system", content=ATS_SYSTEM),
            LLMMessage(
                role="user",
                content=ats_scoring_prompt(resume.raw_text, jd.raw_text),
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
            logger.warning("LLM ATS JSON parse failed", extra={"error": str(e)})
            return {}
        except Exception as e:
            logger.error("LLM ATS call failed", extra={"error": str(e)})
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
    ) -> ATSResult:
        """
        Merge deterministic and LLM results into a final ATSResult.

        Merge strategy:
        - keyword_match_score: deterministic (exact and reproducible)
        - skills_match_score:  deterministic (exact and reproducible)
        - experience_match_score: LLM if available, else estimated
        - education_match_score:  LLM if available, else estimated
        - overall_score: weighted average of the four components
        - matched/missing keywords: deterministic (more precise)
        - recommendations: LLM (richer prose); fallback to generated ones
        - overall_score override: if LLM returns a reasonable overall score
          and deterministic gives 0 (e.g. no skills extracted from JD),
          prefer the LLM score.

        Args:
            resume: Source resume.
            jd: Source job description.
            det: Deterministic analysis dict.
            llm: LLM analysis dict (may be empty).

        Returns:
            Validated ATSResult.
        """
        # Component scores
        keyword_score = det["keyword_score"]
        skills_score = det["skills_score"]

        # Experience score: LLM value if in [0,100], else estimate from resume
        exp_score_raw = self._safe_float(
            (llm.get("breakdown") or {}).get("experience_match_score")
        )
        experience_score = (
            exp_score_raw if exp_score_raw is not None
            else self._estimate_experience_score(resume, jd)
        )

        # Education score: LLM value if available, else simple heuristic
        edu_score_raw = self._safe_float(
            (llm.get("breakdown") or {}).get("education_match_score")
        )
        education_score = (
            edu_score_raw if edu_score_raw is not None
            else self._estimate_education_score(resume, jd)
        )

        # Weighted overall score
        weighted = (
            keyword_score    * SCORE_WEIGHTS["keyword_match"]
            + skills_score   * SCORE_WEIGHTS["skills_match"]
            + experience_score * SCORE_WEIGHTS["experience_match"]
            + education_score  * SCORE_WEIGHTS["education_match"]
        )

        # If LLM returned a plausible overall score, blend it in (60% weighted / 40% LLM)
        llm_overall = self._safe_float(llm.get("overall_score"))
        if llm_overall is not None and 0.0 <= llm_overall <= 100.0:
            overall_score = round(0.6 * weighted + 0.4 * llm_overall, 1)
        else:
            overall_score = round(weighted, 1)

        # Cap to valid range
        overall_score = max(0.0, min(100.0, overall_score))

        # Keywords: prefer deterministic results; supplement with LLM extras
        matched_kw = det["matched_keywords"]
        missing_kw = det["missing_keywords"]

        # Add any LLM-identified matched/missing keywords not already captured
        llm_matched = self._safe_str_list(llm.get("matched_keywords"))
        llm_missing = self._safe_str_list(llm.get("missing_keywords"))
        matched_set = {k.lower() for k in matched_kw}
        missing_set = {k.lower() for k in missing_kw}

        for kw in llm_matched:
            if kw.lower() not in matched_set:
                matched_kw.append(kw)
        matched_set |= {k.lower() for k in llm_matched}
        for kw in llm_missing:
            if kw.lower() not in missing_set and kw.lower() not in matched_set:
                missing_kw.append(kw)

        # The LLM is synonym-aware, so a keyword it found in the resume is not
        # missing even if exact string matching failed to find it.
        missing_kw = [k for k in missing_kw if k.lower() not in matched_set]

        # Recommendations: LLM if available, else generate basic ones
        recommendations = self._safe_str_list(llm.get("recommendations"))
        if not recommendations:
            recommendations = self._generate_fallback_recommendations(
                missing_keywords=missing_kw,
                overall_score=overall_score,
            )

        return ATSResult(
            resume_id=resume.resume_id,
            jd_id=jd.jd_id,
            overall_score=overall_score,
            breakdown=ATSScoreBreakdown(
                keyword_match_score=round(keyword_score, 1),
                skills_match_score=round(skills_score, 1),
                experience_match_score=round(experience_score, 1),
                education_match_score=round(education_score, 1),
            ),
            matched_keywords=matched_kw,
            missing_keywords=missing_kw,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------ #
    #  Score estimation helpers (used when LLM data is unavailable)      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_experience_score(resume: Resume, jd: JobDescription) -> float:
        """
        Estimate experience alignment without LLM.

        Simple heuristic: years mentioned in resume vs JD minimum.
        Falls back to 50.0 (neutral) when neither has year data.
        """
        if not resume.experience:
            return 30.0   # No experience listed — below average

        resume_years = len(resume.experience) * 1.5   # Rough proxy
        jd_min = jd.experience_years_min or 0

        if jd_min == 0:
            return 70.0   # JD has no minimum — assume reasonable fit

        ratio = min(resume_years / jd_min, 1.5) / 1.5
        return round(ratio * 100, 1)

    @staticmethod
    def _estimate_education_score(resume: Resume, jd: JobDescription) -> float:
        """
        Estimate education alignment without LLM.

        Checks whether the JD's required education level appears
        anywhere in the resume's education section.
        """
        if not jd.required_education:
            return 70.0   # No education requirement stated

        if not resume.education:
            return 30.0   # No education listed in resume

        jd_edu_lower = jd.required_education.lower()
        for edu in resume.education:
            degree_lower = edu.degree.lower()
            # Check for common degree keywords
            if any(
                kw in degree_lower
                for kw in ["bachelor", "master", "phd", "b.e", "b.tech", "m.tech", "mba"]
            ):
                if any(
                    kw in jd_edu_lower
                    for kw in ["bachelor", "master", "phd", "b.e", "b.tech", "m.tech"]
                ):
                    return 85.0
                return 70.0

        return 50.0

    @staticmethod
    def _generate_fallback_recommendations(
        missing_keywords: list[str],
        overall_score: float,
    ) -> list[str]:
        """
        Generate basic recommendations when LLM is unavailable.

        Args:
            missing_keywords: Keywords absent from the resume.
            overall_score: Overall ATS match score.

        Returns:
            List of actionable recommendation strings.
        """
        recs: list[str] = []

        if missing_keywords:
            top_missing = missing_keywords[:3]
            recs.append(
                f"Add these missing keywords to your resume: "
                f"{', '.join(top_missing)}."
            )

        if overall_score < 40:
            recs.append(
                "Your resume needs significant keyword alignment with this JD. "
                "Consider rewriting your summary to mirror the job title and "
                "required skills."
            )
        elif overall_score < 60:
            recs.append(
                "Improve keyword coverage by tailoring your skills section to "
                "match the job description more closely."
            )
        else:
            recs.append(
                "Good match! Strengthen further by quantifying achievements "
                "and adding any missing technical keywords."
            )

        recs.append(
            "Ensure your resume uses the exact tool and technology names from "
            "the JD — ATS systems often require exact matches."
        )

        return recs

    # ------------------------------------------------------------------ #
    #  Utility helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """
        Normalise text to a set of lowercase alphanumeric tokens.

        Handles compound terms like "LangChain", "ChromaDB", "GPT-4"
        by splitting on whitespace and common separators, lowercasing,
        and removing pure punctuation tokens.
        """
        # Split on whitespace and common separators
        raw_tokens = re.split(r"[\s,;:()\[\]{}/\\]+", text.lower())
        return {
            t.strip(".-_\"'")
            for t in raw_tokens
            if t.strip(".-_\"'") and len(t) > 1
        }

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        """Return float in [0, 100] or None."""
        if value is None:
            return None
        try:
            f = float(value)
            return f if 0.0 <= f <= 100.0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str_list(value: object) -> list[str]:
        """Return list of non-empty strings or []."""
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if v and str(v).strip()]
