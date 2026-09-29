"""
Streamlit Session State Manager.

Centralises all session_state keys so pages never use raw string keys.
Prevents key-name typos and makes state schema discoverable.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from core.domain.analysis import ATSResult, ResumeImprovementReport, SkillGapResult
from core.domain.interview import InterviewQuestionSet, MockInterviewSession
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.services.analytics_service import AnalyticsReport
from core.services.conversation_memory import ConversationMemoryService


# ── Key constants ──────────────────────────────────────────────────
_RESUME         = "resume"
_JD             = "jd"
_ATS_RESULT     = "ats_result"
_SKILL_GAP      = "skill_gap"
_IMPROVEMENT    = "improvement_report"
_QUESTION_SET   = "question_set"
_MOCK_SESSION   = "mock_session"
_ANALYTICS      = "analytics_report"
_MEMORY         = "conversation_memory"
_ACTIVE_PAGE    = "active_page"
_SESSION_ID     = "session_id"


def init_session() -> None:
    """
    Initialise all session state keys with safe defaults.

    Called once at the top of main.py before any page renders.
    Idempotent — safe to call on every re-run.
    """
    import uuid

    defaults: dict = {
        _RESUME:        None,
        _JD:            None,
        _ATS_RESULT:    None,
        _SKILL_GAP:     None,
        _IMPROVEMENT:   None,
        _QUESTION_SET:  None,
        _MOCK_SESSION:  None,
        _ANALYTICS:     None,
        _MEMORY:        None,
        _ACTIVE_PAGE:   "upload",
        _SESSION_ID:    str(uuid.uuid4()),
    }

    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # Initialise conversation memory once
    if st.session_state[_MEMORY] is None:
        st.session_state[_MEMORY] = ConversationMemoryService()


# ── Typed accessors ────────────────────────────────────────────────

def get_resume() -> Optional[Resume]:
    return st.session_state.get(_RESUME)

def set_resume(resume: Resume) -> None:
    st.session_state[_RESUME] = resume

def get_jd() -> Optional[JobDescription]:
    return st.session_state.get(_JD)

def set_jd(jd: JobDescription) -> None:
    st.session_state[_JD] = jd

def get_ats_result() -> Optional[ATSResult]:
    return st.session_state.get(_ATS_RESULT)

def set_ats_result(result: ATSResult) -> None:
    st.session_state[_ATS_RESULT] = result

def get_skill_gap() -> Optional[SkillGapResult]:
    return st.session_state.get(_SKILL_GAP)

def set_skill_gap(result: SkillGapResult) -> None:
    st.session_state[_SKILL_GAP] = result

def get_improvement() -> Optional[ResumeImprovementReport]:
    return st.session_state.get(_IMPROVEMENT)

def set_improvement(report: ResumeImprovementReport) -> None:
    st.session_state[_IMPROVEMENT] = report

def get_question_set() -> Optional[InterviewQuestionSet]:
    return st.session_state.get(_QUESTION_SET)

def set_question_set(qs: InterviewQuestionSet) -> None:
    st.session_state[_QUESTION_SET] = qs

def get_mock_session() -> Optional[MockInterviewSession]:
    return st.session_state.get(_MOCK_SESSION)

def set_mock_session(session: MockInterviewSession) -> None:
    st.session_state[_MOCK_SESSION] = session

def get_analytics() -> Optional[AnalyticsReport]:
    return st.session_state.get(_ANALYTICS)

def set_analytics(report: AnalyticsReport) -> None:
    st.session_state[_ANALYTICS] = report

def get_memory() -> ConversationMemoryService:
    return st.session_state[_MEMORY]

def get_session_id() -> str:
    return st.session_state[_SESSION_ID]

def get_active_page() -> str:
    return st.session_state.get(_ACTIVE_PAGE, "upload")

def set_active_page(page: str) -> None:
    st.session_state[_ACTIVE_PAGE] = page

def is_ready() -> bool:
    """True when both resume and JD have been uploaded and parsed."""
    return get_resume() is not None and get_jd() is not None

def reset_analysis() -> None:
    """Clear all analysis results (but keep resume/JD)."""
    for key in [_ATS_RESULT, _SKILL_GAP, _IMPROVEMENT,
                _QUESTION_SET, _MOCK_SESSION, _ANALYTICS]:
        st.session_state[key] = None
