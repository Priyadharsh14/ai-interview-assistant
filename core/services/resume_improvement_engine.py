"""
Resume Improvement Engine.

Analyses a resume against a job description and produces section-level
improvement suggestions with priority rankings.

Two-layer strategy:
    Layer 1 — Rule-based structural audit:
        Checks for common resume weaknesses without LLM:
        - Missing or thin summary section
        - No quantified achievements in experience descriptions
        - Skills section not aligned with JD keywords
        - Missing contact fields
        - Education section completeness
        Produces high-confidence, deterministic flags.

    Layer 2 — LLM-enhanced content analysis:
        Sends resume + JD to Groq/Llama 3.3 for deep content review:
        - Weak action verbs
        - Vague descriptions that could be sharpened
        - Missing keywords that would improve ATS match
        - Tailoring opportunities for this specific JD
        Produces richer, context-aware suggestions.

Merge strategy:
    Rule-based findings are always included (high precision).
    LLM suggestions are appended and deduplicated by section.
    Combined list is sorted by priority (high → medium → low).
    Overall feedback always comes from LLM (more fluent prose).
"""

from __future__ import annotations

import re
from typing import Optional

from config.logging_config import get_logger
from core.domain.analysis import ResumeImprovement, ResumeImprovementReport
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from infrastructure.llm.json_parser import LLMJSONParseError, parse_llm_json
from infrastructure.llm.prompt_templates import (
    RESUME_IMPROVEMENT_SYSTEM,
    resume_improvement_prompt,
)

logger = get_logger(__name__)

# Priority ordering for sorting
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Minimum word count thresholds for resume sections
MIN_SUMMARY_WORDS = 30
MIN_EXPERIENCE_DESC_WORDS = 20

# Patterns that signal quantified achievements
_QUANTIFIER_PATTERNS = [
    re.compile(r"\d+\s*%"),           # percentages
    re.compile(r"\$\s*\d+"),          # dollar amounts
    re.compile(r"\d+[kKmMbB]"),       # abbreviated numbers (50k, 2M)
    re.compile(r"\d+x\b"),            # multipliers (3x)
    re.compile(r"\b\d+\s+(users?|customers?|clients?|engineers?|teams?)",
               re.IGNORECASE),
    re.compile(r"reduced|increased|improved|grew|cut|saved|delivered",
               re.IGNORECASE),
]


class ResumeImprovementEngine:
    """
    Generates section-level resume improvement suggestions.

    Returns a ResumeImprovementReport containing:
    - improvements: list of ResumeImprovement (section, issue, suggestion, priority)
    - overall_feedback: 2–3 sentence holistic assessment

    Usage:
        engine = ResumeImprovementEngine(llm=groq_provider)
        report = engine.improve(resume, job_description)
        for item in report.improvements:
            print(f"[{item.priority.upper()}] {item.section}: {item.suggestion}")
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self._llm = llm
        logger.debug("ResumeImprovementEngine initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def improve(
        self,
        resume: Resume,
        jd: Optional[JobDescription] = None,
    ) -> ResumeImprovementReport:
        """
        Analyse a resume and return improvement suggestions.

        Args:
            resume: Parsed Resume domain model.
            jd: Optional JobDescription — enables JD-targeted suggestions.
                When None, analysis focuses on general resume quality.

        Returns:
            ResumeImprovementReport with prioritised improvements.
        """
        logger.info(
            "Generating resume improvements",
            extra={
                "resume_id": resume.resume_id,
                "jd_id": jd.jd_id if jd else "none",
            },
        )

        # Layer 1: deterministic structural audit
        rule_improvements = self._rule_based_audit(resume, jd)

        # Layer 2: LLM content analysis
        llm_data = self._llm_analysis(resume, jd)

        # Merge and build final report
        report = self._build_report(resume, jd, rule_improvements, llm_data)

        logger.info(
            "Resume improvement analysis complete",
            extra={
                "resume_id": resume.resume_id,
                "improvements": len(report.improvements),
            },
        )
        return report

    # ------------------------------------------------------------------ #
    #  Layer 1: Rule-based structural audit                               #
    # ------------------------------------------------------------------ #

    def _rule_based_audit(
        self,
        resume: Resume,
        jd: Optional[JobDescription],
    ) -> list[ResumeImprovement]:
        """
        Check for common, detectable resume weaknesses without LLM.

        Each check is independent — a failure in one doesn't skip others.
        Returns a list of ResumeImprovement instances ready for merging.
        """
        improvements: list[ResumeImprovement] = []

        improvements.extend(self._check_contact_info(resume))
        improvements.extend(self._check_summary(resume))
        improvements.extend(self._check_skills_alignment(resume, jd))
        improvements.extend(self._check_experience_quality(resume))
        improvements.extend(self._check_education(resume))
        improvements.extend(self._check_overall_completeness(resume))

        return improvements

    def _check_contact_info(self, resume: Resume) -> list[ResumeImprovement]:
        issues = []
        if not resume.contact.linkedin:
            issues.append(ResumeImprovement(
                section="Contact",
                issue="LinkedIn profile URL is missing.",
                suggestion=(
                    "Add your LinkedIn profile URL. Recruiters verify "
                    "candidates on LinkedIn before shortlisting."
                ),
                priority="medium",
            ))
        if not resume.contact.email:
            issues.append(ResumeImprovement(
                section="Contact",
                issue="Email address is missing.",
                suggestion=(
                    "Include a professional email address at the top of your resume."
                ),
                priority="high",
            ))
        if not resume.contact.github and resume.technical_skills:
            issues.append(ResumeImprovement(
                section="Contact",
                issue="GitHub profile is missing for a technical role.",
                suggestion=(
                    "Add your GitHub URL. For engineering roles, a GitHub "
                    "profile with active repos significantly strengthens your application."
                ),
                priority="medium",
            ))
        return issues

    def _check_summary(self, resume: Resume) -> list[ResumeImprovement]:
        issues = []
        if not resume.summary:
            issues.append(ResumeImprovement(
                section="Summary",
                issue="Professional summary section is missing.",
                suggestion=(
                    "Add a 3–4 sentence summary that highlights your years of "
                    "experience, key technical skills, and career focus. This is "
                    "the first thing a recruiter reads."
                ),
                priority="high",
            ))
        elif len(resume.summary.split()) < MIN_SUMMARY_WORDS:
            issues.append(ResumeImprovement(
                section="Summary",
                issue=f"Summary is too brief ({len(resume.summary.split())} words).",
                suggestion=(
                    "Expand your summary to 40–60 words. Mention your specialisation, "
                    "key tools, and a notable achievement or career goal."
                ),
                priority="medium",
            ))
        return issues

    def _check_skills_alignment(
        self,
        resume: Resume,
        jd: Optional[JobDescription],
    ) -> list[ResumeImprovement]:
        issues = []

        if not resume.skills and not resume.technical_skills:
            issues.append(ResumeImprovement(
                section="Skills",
                issue="No skills section detected.",
                suggestion=(
                    "Add a dedicated Skills section listing technical tools, "
                    "languages, frameworks, and platforms. ATS systems scan "
                    "this section first."
                ),
                priority="high",
            ))
            return issues

        if jd:
            resume_skills_lower = {
                s.lower() for s in resume.skills + resume.technical_skills
            }
            jd_required_lower = {s.lower() for s in jd.required_skills}
            missing = jd_required_lower - resume_skills_lower
            if missing:
                top_missing = sorted(missing)[:4]
                issues.append(ResumeImprovement(
                    section="Skills",
                    issue=(
                        f"Required JD skills missing from Skills section: "
                        f"{', '.join(top_missing)}."
                    ),
                    suggestion=(
                        f"Add these skills explicitly: {', '.join(top_missing)}. "
                        "Even if you have experience with them, ATS systems "
                        "need to find the exact keyword."
                    ),
                    priority="high",
                ))

        return issues

    def _check_experience_quality(self, resume: Resume) -> list[ResumeImprovement]:
        issues = []

        if not resume.experience:
            issues.append(ResumeImprovement(
                section="Experience",
                issue="No work experience entries found.",
                suggestion=(
                    "Add at least one work experience entry. Include internships, "
                    "freelance work, or significant academic projects if you're "
                    "early in your career."
                ),
                priority="high",
            ))
            return issues

        unquantified = []
        for exp in resume.experience:
            if len(exp.description.split()) < MIN_EXPERIENCE_DESC_WORDS:
                issues.append(ResumeImprovement(
                    section="Experience",
                    issue=(
                        f"Experience at {exp.company} has a very short description "
                        f"({len(exp.description.split())} words)."
                    ),
                    suggestion=(
                        f"Expand the description for {exp.company} to 3–5 bullet points "
                        "covering: what you built, technologies used, and measurable impact."
                    ),
                    priority="medium",
                ))

            if not any(p.search(exp.description) for p in _QUANTIFIER_PATTERNS):
                unquantified.append(exp.company)

        if unquantified:
            companies = ", ".join(unquantified[:3])
            issues.append(ResumeImprovement(
                section="Experience",
                issue=(
                    f"Experience descriptions lack quantified achievements "
                    f"({companies})."
                ),
                suggestion=(
                    "Add metrics to your bullet points: 'Reduced API latency by 40%', "
                    "'Served 10k daily users', 'Cut deployment time from 2 hours to 15 minutes'. "
                    "Numbers make achievements concrete and memorable."
                ),
                priority="high",
            ))

        return issues

    def _check_education(self, resume: Resume) -> list[ResumeImprovement]:
        issues = []
        if not resume.education:
            issues.append(ResumeImprovement(
                section="Education",
                issue="No education entries found.",
                suggestion=(
                    "Add your educational background including degree, institution, "
                    "and graduation year. Even if self-taught, mention relevant "
                    "certifications or bootcamps."
                ),
                priority="medium",
            ))
        return issues

    def _check_overall_completeness(self, resume: Resume) -> list[ResumeImprovement]:
        issues = []
        word_count = resume.word_count

        if word_count < 200:
            issues.append(ResumeImprovement(
                section="Overall",
                issue=f"Resume is very short ({word_count} words).",
                suggestion=(
                    "A strong resume for an engineering role is typically 400–700 words "
                    "(1 page). Expand experience descriptions and add a projects section."
                ),
                priority="high",
            ))
        elif word_count > 1200:
            issues.append(ResumeImprovement(
                section="Overall",
                issue=f"Resume may be too long ({word_count} words).",
                suggestion=(
                    "Aim for 1 page (under 700 words) for less than 5 years of experience, "
                    "2 pages maximum for senior roles. Remove outdated or irrelevant entries."
                ),
                priority="low",
            ))

        if not resume.projects and not resume.certifications:
            issues.append(ResumeImprovement(
                section="Projects",
                issue="No projects or certifications listed.",
                suggestion=(
                    "Add 2–3 portfolio projects with a brief description and a GitHub link. "
                    "For GenAI roles, a working RAG or LLM app is highly valued."
                ),
                priority="medium",
            ))

        return issues

    # ------------------------------------------------------------------ #
    #  Layer 2: LLM content analysis                                     #
    # ------------------------------------------------------------------ #

    def _llm_analysis(
        self,
        resume: Resume,
        jd: Optional[JobDescription],
    ) -> dict:
        """
        Call LLM for deep content analysis.

        Handles nuances that rules cannot:
        - Weak action verbs ("worked on" → "engineered")
        - Vague descriptions ("improved performance" → specify by how much)
        - Keyword injection opportunities specific to this JD
        - Writing quality and tone

        Falls back to empty dict on any failure.
        """
        jd_text = jd.raw_text if jd else "No specific job description provided."
        messages = [
            LLMMessage(role="system", content=RESUME_IMPROVEMENT_SYSTEM),
            LLMMessage(
                role="user",
                content=resume_improvement_prompt(resume.raw_text, jd_text),
            ),
        ]
        try:
            response = self._llm.generate(
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
            )
            return parse_llm_json(response.content)
        except LLMJSONParseError as e:
            logger.warning("LLM improvement JSON parse failed", extra={"error": str(e)})
            return {}
        except Exception as e:
            logger.error("LLM improvement call failed", extra={"error": str(e)})
            return {}

    # ------------------------------------------------------------------ #
    #  Result assembly                                                    #
    # ------------------------------------------------------------------ #

    def _build_report(
        self,
        resume: Resume,
        jd: Optional[JobDescription],
        rule_improvements: list[ResumeImprovement],
        llm_data: dict,
    ) -> ResumeImprovementReport:
        """
        Merge rule-based and LLM improvements into a final report.

        Merge strategy:
        1. Start with all rule-based improvements (high precision)
        2. Parse LLM improvements and add non-duplicate ones
        3. Deduplicate by (section, issue) normalised key
        4. Sort by priority: high → medium → low
        5. Overall feedback from LLM; fallback to generated summary

        Args:
            resume: Source resume.
            jd: Source JD (may be None).
            rule_improvements: Deterministic findings.
            llm_data: LLM response dict (may be empty).

        Returns:
            Validated ResumeImprovementReport.
        """
        # Parse LLM improvements
        llm_improvements = self._parse_llm_improvements(
            llm_data.get("improvements") or []
        )

        # Merge: rule-based first, then LLM extras
        seen: set[str] = set()
        merged: list[ResumeImprovement] = []

        for imp in rule_improvements + llm_improvements:
            key = f"{imp.section.lower()}|{imp.issue[:40].lower()}"
            if key not in seen:
                seen.add(key)
                merged.append(imp)

        # Sort by priority
        merged.sort(key=lambda i: _PRIORITY_ORDER.get(i.priority.lower(), 1))

        # Overall feedback
        overall_feedback = (
            str(llm_data.get("overall_feedback", "")).strip()
            or self._generate_fallback_feedback(resume, len(merged))
        )

        return ResumeImprovementReport(
            resume_id=resume.resume_id,
            jd_id=jd.jd_id if jd else None,
            improvements=merged,
            overall_feedback=overall_feedback,
        )

    @staticmethod
    def _parse_llm_improvements(raw: object) -> list[ResumeImprovement]:
        """
        Parse the LLM improvements list into ResumeImprovement objects.

        Silently skips malformed entries — LLMs occasionally omit required fields.
        """
        if not isinstance(raw, list):
            return []

        improvements = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                imp = ResumeImprovement(
                    section=str(item.get("section") or "General").strip(),
                    issue=str(item.get("issue") or "").strip(),
                    suggestion=str(item.get("suggestion") or "").strip(),
                    priority=str(item.get("priority") or "medium").lower().strip(),
                )
                if imp.issue and imp.suggestion:
                    improvements.append(imp)
            except Exception:
                continue

        return improvements

    @staticmethod
    def _generate_fallback_feedback(resume: Resume, issue_count: int) -> str:
        """Generate a basic overall feedback summary when LLM is unavailable."""
        if issue_count == 0:
            return (
                "Your resume looks well-structured. Consider tailoring the "
                "Skills section and Summary to each specific job description "
                "for better ATS match rates."
            )
        elif issue_count <= 3:
            return (
                f"Your resume has {issue_count} area(s) that could be strengthened. "
                "Address the high-priority items first, particularly around "
                "skills alignment and quantified achievements."
            )
        else:
            return (
                f"Your resume has {issue_count} improvement opportunities identified. "
                "Start with the high-priority items: ensure all required skills are "
                "listed, add metrics to your experience, and write a strong summary."
            )
