"""
Analytics Service.

Aggregates data from ATS, Skill Gap, Resume Improvement, and Mock Interview
services into a unified AnalyticsReport.

Design:
    - Pure computation: no LLM calls, no I/O, no external dependencies
    - All inputs are typed domain objects already computed by other services
    - Outputs are typed dataclasses consumed directly by the Streamlit UI
    - Stateless: called on-demand each time the dashboard renders

Dashboard cards this service powers:
    - ATS Score card           ← ATSResult
    - Resume Strength card     ← ATSResult + ResumeImprovementReport
    - Missing Skills card      ← SkillGapResult
    - Interview Readiness card ← MockInterviewSession(s) + SkillGapResult
    - Study Progress card      ← StudyRoadmap (future phases)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config.logging_config import get_logger
from core.domain.analysis import ATSResult, ResumeImprovementReport, SkillGapResult
from core.domain.interview import MockInterviewSession

logger = get_logger(__name__)


# ------------------------------------------------------------------ #
#  Report domain objects                                              #
# ------------------------------------------------------------------ #

@dataclass
class ATSMetrics:
    """ATS scoring summary for the dashboard."""
    overall_score: float            # 0–100
    score_label: str                # Excellent / Good / Fair / Needs Work
    keyword_match_score: float
    skills_match_score: float
    experience_match_score: float
    education_match_score: float
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    top_recommendations: list[str] = field(default_factory=list)

    @property
    def score_colour(self) -> str:
        """CSS colour hint for the dashboard card."""
        if self.overall_score >= 80:
            return "#22c55e"   # green
        if self.overall_score >= 60:
            return "#3b82f6"   # blue
        if self.overall_score >= 40:
            return "#f59e0b"   # amber
        return "#ef4444"       # red


@dataclass
class SkillMetrics:
    """Skill gap summary for the dashboard."""
    skill_match_percentage: float
    matched_skills: list[str] = field(default_factory=list)
    missing_technical_skills: list[str] = field(default_factory=list)
    missing_soft_skills: list[str] = field(default_factory=list)
    total_missing: int = 0
    top_recommendations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.total_missing = (
            len(self.missing_technical_skills) + len(self.missing_soft_skills)
        )


@dataclass
class ResumeStrengthMetrics:
    """Resume quality summary for the dashboard."""
    strength_score: float           # 0–100 computed from improvement findings
    high_priority_issues: int
    medium_priority_issues: int
    low_priority_issues: int
    overall_feedback: str = ""
    top_improvements: list[str] = field(default_factory=list)

    @property
    def strength_label(self) -> str:
        if self.strength_score >= 80:
            return "Strong"
        if self.strength_score >= 60:
            return "Good"
        if self.strength_score >= 40:
            return "Fair"
        return "Needs Work"


@dataclass
class InterviewReadinessMetrics:
    """Interview readiness summary derived from mock sessions."""
    readiness_score: float          # 0–100 blended score
    readiness_label: str            # Ready / Almost Ready / In Progress / Not Started
    sessions_completed: int
    average_score: float            # 0–10 average across all sessions
    best_category: Optional[str]
    weakest_category: Optional[str]
    questions_answered: int
    questions_skipped: int
    recent_trend: str               # "improving" | "stable" | "declining" | "insufficient_data"


@dataclass
class AnalyticsReport:
    """
    Complete analytics report for one resume+JD pairing.

    Produced by AnalyticsService.generate_report() and consumed
    directly by the Streamlit dashboard page.
    """
    ats: Optional[ATSMetrics] = None
    skills: Optional[SkillMetrics] = None
    resume_strength: Optional[ResumeStrengthMetrics] = None
    interview_readiness: Optional[InterviewReadinessMetrics] = None

    @property
    def has_ats_data(self) -> bool:
        return self.ats is not None

    @property
    def has_skills_data(self) -> bool:
        return self.skills is not None

    @property
    def has_resume_data(self) -> bool:
        return self.resume_strength is not None

    @property
    def has_interview_data(self) -> bool:
        return self.interview_readiness is not None

    @property
    def overall_readiness_score(self) -> float:
        """
        Composite readiness score across all available data sources.

        Weights:
            ATS score       : 30%
            Skill match     : 30%
            Resume strength : 20%
            Interview score : 20%
        """
        components: list[tuple[float, float]] = []

        if self.ats:
            components.append((self.ats.overall_score, 0.30))
        if self.skills:
            components.append((self.skills.skill_match_percentage, 0.30))
        if self.resume_strength:
            components.append((self.resume_strength.strength_score, 0.20))
        if self.interview_readiness:
            # Convert 0–10 interview score to 0–100
            components.append((self.interview_readiness.average_score * 10, 0.20))

        if not components:
            return 0.0

        # Normalise weights to sum to 1.0 across available components
        total_weight = sum(w for _, w in components)
        return round(
            sum(score * (w / total_weight) for score, w in components),
            1,
        )


# ------------------------------------------------------------------ #
#  Service                                                            #
# ------------------------------------------------------------------ #

class AnalyticsService:
    """
    Aggregates domain results into a unified AnalyticsReport.

    Pure computation — no LLM, no I/O. Takes already-computed domain
    objects and transforms them into dashboard-ready metrics.

    Usage:
        service = AnalyticsService()
        report = service.generate_report(
            ats_result=ats_result,
            skill_gap_result=skill_gap_result,
            improvement_report=improvement_report,
            mock_sessions=[session1, session2],
        )
        print(f"Overall readiness: {report.overall_readiness_score}%")
    """

    def __init__(self) -> None:
        logger.debug("AnalyticsService initialised")

    def generate_report(
        self,
        ats_result: Optional[ATSResult] = None,
        skill_gap_result: Optional[SkillGapResult] = None,
        improvement_report: Optional[ResumeImprovementReport] = None,
        mock_sessions: Optional[list[MockInterviewSession]] = None,
    ) -> AnalyticsReport:
        """
        Produce a complete AnalyticsReport from available data.

        All arguments are optional — the report populates whatever
        sections have data and leaves others as None.

        Args:
            ats_result: Output of ATSEngine.score().
            skill_gap_result: Output of SkillGapEngine.analyse().
            improvement_report: Output of ResumeImprovementEngine.improve().
            mock_sessions: List of MockInterviewSession objects (any state).

        Returns:
            AnalyticsReport with populated metric sections.
        """
        logger.info("Generating analytics report")

        report = AnalyticsReport(
            ats=self._build_ats_metrics(ats_result) if ats_result else None,
            skills=self._build_skill_metrics(skill_gap_result) if skill_gap_result else None,
            resume_strength=(
                self._build_resume_strength(improvement_report)
                if improvement_report else None
            ),
            interview_readiness=(
                self._build_interview_readiness(mock_sessions)
                if mock_sessions else None
            ),
        )

        logger.info(
            "Analytics report generated",
            extra={
                "has_ats": report.has_ats_data,
                "has_skills": report.has_skills_data,
                "has_resume": report.has_resume_data,
                "has_interview": report.has_interview_data,
                "overall_readiness": report.overall_readiness_score,
            },
        )
        return report

    # ------------------------------------------------------------------ #
    #  Section builders                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_ats_metrics(result: ATSResult) -> ATSMetrics:
        """Transform ATSResult → ATSMetrics."""
        return ATSMetrics(
            overall_score=result.overall_score,
            score_label=result.score_label,
            keyword_match_score=result.breakdown.keyword_match_score,
            skills_match_score=result.breakdown.skills_match_score,
            experience_match_score=result.breakdown.experience_match_score,
            education_match_score=result.breakdown.education_match_score,
            matched_keywords=result.matched_keywords[:10],
            missing_keywords=result.missing_keywords[:10],
            top_recommendations=result.recommendations[:3],
        )

    @staticmethod
    def _build_skill_metrics(result: SkillGapResult) -> SkillMetrics:
        """Transform SkillGapResult → SkillMetrics."""
        return SkillMetrics(
            skill_match_percentage=result.skill_match_percentage,
            matched_skills=result.matched_skills,
            missing_technical_skills=result.missing_technical_skills,
            missing_soft_skills=result.missing_soft_skills,
            top_recommendations=result.learning_recommendations[:4],
        )

    @staticmethod
    def _build_resume_strength(report: ResumeImprovementReport) -> ResumeStrengthMetrics:
        """
        Derive a resume strength score from improvement findings.

        Scoring heuristic:
            Start at 100, subtract penalties per issue by priority:
                high   → 12 points each
                medium → 6 points each
                low    → 2 points each
            Clamp to [0, 100].
        """
        high = [i for i in report.improvements if i.priority == "high"]
        medium = [i for i in report.improvements if i.priority == "medium"]
        low = [i for i in report.improvements if i.priority == "low"]

        penalty = len(high) * 12 + len(medium) * 6 + len(low) * 2
        strength_score = max(0.0, min(100.0, 100.0 - penalty))

        top_improvements = [i.suggestion for i in (high + medium)[:3]]

        return ResumeStrengthMetrics(
            strength_score=round(strength_score, 1),
            high_priority_issues=len(high),
            medium_priority_issues=len(medium),
            low_priority_issues=len(low),
            overall_feedback=report.overall_feedback,
            top_improvements=top_improvements,
        )

    @staticmethod
    def _build_interview_readiness(
        sessions: list[MockInterviewSession],
    ) -> InterviewReadinessMetrics:
        """
        Compute interview readiness from one or more mock sessions.

        Readiness score (0–100):
            base = average_score * 10   (converts 0–10 → 0–100)
            sessions_bonus: +5 per completed session (max +15)
            Clamp to [0, 100].

        Trend:
            Requires >= 2 completed sessions.
            "improving"  if last session score > first by > 0.5
            "declining"  if last session score < first by > 0.5
            "stable"     otherwise
        """
        completed = [s for s in sessions if s.is_complete]

        total_answered = sum(len(s.answered_evaluations) for s in sessions)
        total_skipped = sum(
            (len(s.evaluations) - len(s.answered_evaluations)) + s.questions_remaining
            for s in sessions
        )

        if not completed:
            return InterviewReadinessMetrics(
                readiness_score=0.0,
                readiness_label="Not Started",
                sessions_completed=0,
                average_score=0.0,
                best_category=None,
                weakest_category=None,
                questions_answered=total_answered,
                questions_skipped=total_skipped,
                recent_trend="insufficient_data",
            )

        # Average score across all completed sessions
        avg_score = round(
            sum(s.average_score for s in completed) / len(completed), 2
        )

        # Readiness score
        base = avg_score * 10
        sessions_bonus = min(len(completed) * 5, 15)
        readiness_score = round(min(100.0, base + sessions_bonus), 1)

        # Category analysis across all sessions
        best_cat, weakest_cat = AnalyticsService._category_extremes(completed)

        # Trend
        trend = AnalyticsService._compute_trend(completed)

        # Label
        label = (
            "Ready" if readiness_score >= 80
            else "Almost Ready" if readiness_score >= 60
            else "In Progress" if readiness_score >= 30
            else "Not Started"
        )

        return InterviewReadinessMetrics(
            readiness_score=readiness_score,
            readiness_label=label,
            sessions_completed=len(completed),
            average_score=avg_score,
            best_category=best_cat,
            weakest_category=weakest_cat,
            questions_answered=total_answered,
            questions_skipped=total_skipped,
            recent_trend=trend,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _category_extremes(
        sessions: list[MockInterviewSession],
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Find the best and weakest question categories across sessions.

        Returns (best_category_name, weakest_category_name).
        """
        from core.domain.interview import QuestionType

        type_scores: dict[str, list[float]] = {}

        for session in sessions:
            eval_by_qid = {e.question_id: e for e in session.evaluations}
            for q in session.questions:
                ev = eval_by_qid.get(q.question_id)
                if ev and ev.candidate_answer != "[SKIPPED]":
                    cat = q.question_type.value.replace("_", " ").title()
                    type_scores.setdefault(cat, []).append(ev.score)

        if not type_scores:
            return None, None

        averages = {
            cat: sum(scores) / len(scores)
            for cat, scores in type_scores.items()
        }

        best = max(averages, key=lambda k: averages[k])
        weakest = min(averages, key=lambda k: averages[k])

        return best, weakest

    @staticmethod
    def _compute_trend(
        completed_sessions: list[MockInterviewSession],
    ) -> str:
        """
        Compute performance trend across completed sessions.

        Compares the earliest and latest session scores.
        Requires at least 2 completed sessions.
        """
        if len(completed_sessions) < 2:
            return "insufficient_data"

        # Sort by started_at to get chronological order
        sorted_sessions = sorted(
            completed_sessions,
            key=lambda s: s.started_at,
        )

        first_score = sorted_sessions[0].average_score
        last_score = sorted_sessions[-1].average_score
        delta = last_score - first_score

        if delta > 0.5:
            return "improving"
        if delta < -0.5:
            return "declining"
        return "stable"

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, value))
