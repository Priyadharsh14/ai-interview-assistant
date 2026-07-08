"""Resume Improvement page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def render() -> None:
    st.markdown(cards.section_header("✏️ Resume Improvements"), unsafe_allow_html=True)
    if not session_state.is_ready():
        st.markdown(cards.empty_state("✏️","Upload documents first",""), unsafe_allow_html=True)
        return

    report = session_state.get_improvement()
    if report is None:
        if st.button("Generate Improvement Report", use_container_width=True):
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

    priority_colours = {
        "high":   ("#ef4444", "rgba(239,68,68,.15)",  "rgba(239,68,68,.3)"),
        "medium": ("#f59e0b", "rgba(245,158,11,.15)", "rgba(245,158,11,.3)"),
        "low":    ("#3b82f6", "rgba(59,130,246,.15)",  "rgba(59,130,246,.3)"),
    }

    for imp in report.improvements:
        colour, bg, border = priority_colours.get(
            imp.priority.lower(), ("#94a3b8", "rgba(148,163,184,.1)", "rgba(148,163,184,.2)")
        )
        label = imp.priority.upper()

        with st.expander(f"[{label}] {imp.section}: {imp.issue[:70]}"):
            st.markdown(
                f'<span style="border-radius:999px;padding:.15rem .6rem;'
                f'font-size:.75rem;font-weight:700;background:{bg};'
                f'color:{colour};border:1px solid {border}">{label}</span>',
                unsafe_allow_html=True,
            )
            st.markdown(f"**Section:** {imp.section}")
            st.markdown(f"**Issue:** {imp.issue}")
            st.markdown(f"**Fix:** {imp.suggestion}")
