"""Resume Improvement page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def _short(text: str, limit: int) -> str:
    """Trim to `limit` characters at a word boundary, adding an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def render() -> None:
    st.markdown(
        cards.page_header(
            "Resume tips",
            "Specific, prioritised changes that would make your resume stronger for this role.",
            kicker="Analysis",
        ),
        unsafe_allow_html=True,
    )
    if not session_state.is_ready():
        st.markdown(cards.empty_state("Upload documents first", "Add your resume and a job description on the Upload Documents page."), unsafe_allow_html=True)
        return

    report = session_state.get_improvement()
    if report is None:
        if st.button("Generate Improvement Report", type="primary", use_container_width=True):
            with st.spinner("Analysing resume…"):
                report = service_factory.get_improvement_engine().improve(
                    session_state.get_resume(), session_state.get_jd()
                )
                session_state.set_improvement(report)
                st.rerun()
        return

    if report.overall_feedback:
        st.info(report.overall_feedback)

    st.markdown(
        cards.section_header(f"Improvements ({len(report.improvements)} found)"),
        unsafe_allow_html=True,
    )

    for imp in report.improvements:
        label = imp.priority.upper()

        with st.expander(f"[{label}] {imp.section}: {_short(imp.issue, 80)}"):
            st.markdown(cards.badge(imp.priority, imp.priority.lower()), unsafe_allow_html=True)
            st.markdown(f"**Section:** {imp.section}")
            st.markdown(f"**Issue:** {imp.issue}")
            st.markdown(f"**Fix:** {imp.suggestion}")
