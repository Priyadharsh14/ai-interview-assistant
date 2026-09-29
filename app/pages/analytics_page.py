"""Analytics page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def render() -> None:
    st.markdown(
        cards.page_header(
            "Analytics",
            "One composite readiness score built from your analyses and practice sessions.",
            kicker="Overview",
        ),
        unsafe_allow_html=True,
    )
    if not session_state.is_ready():
        st.markdown(cards.empty_state("Upload documents first", "Add your resume and a job description on the Upload Documents page."), unsafe_allow_html=True)
        return

    # Rebuilt on every visit (no LLM call) so it reflects the latest analyses
    # and mock interview rather than whatever existed when it was first built.
    analytics = service_factory.get_analytics_service().generate_report(
        ats_result=session_state.get_ats_result(),
        skill_gap_result=session_state.get_skill_gap(),
        improvement_report=session_state.get_improvement(),
        mock_sessions=[session_state.get_mock_session()] if session_state.get_mock_session() else None,
    )
    session_state.set_analytics(analytics)

    overall = analytics.overall_readiness_score
    colour = "green" if overall >= 80 else "blue" if overall >= 60 else "amber" if overall >= 40 else "red"
    g_col, b_col = st.columns([1, 2], gap="large")
    with g_col:
        st.markdown(cards.gauge(overall, "Overall readiness", "Composite score", colour),
                    unsafe_allow_html=True)
    with b_col:
        rows = ""
        if analytics.has_ats_data:
            rows += cards.bar_row("ATS match", analytics.ats.overall_score)
        if analytics.has_resume_data:
            rows += cards.bar_row("Resume strength", analytics.resume_strength.strength_score)
        if analytics.has_skills_data:
            rows += cards.bar_row("Skill match", analytics.skills.skill_match_percentage)
        if analytics.has_interview_data:
            rows += cards.bar_row("Interview readiness", analytics.interview_readiness.readiness_score)
        if not rows:
            rows = '<p class="card-note">Run the analysis on the Dashboard to see the components.</p>'
        st.markdown(
            f'<div class="panel pad-lg"><div class="card-title">What makes up the score</div>{rows}</div>',
            unsafe_allow_html=True,
        )

    if analytics.has_interview_data:
        ir = analytics.interview_readiness
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Interview Performance", sub=True), unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(cards.metric_card("Sessions Done", str(ir.sessions_completed), ""), unsafe_allow_html=True)
        with c2:
            st.markdown(cards.metric_card("Avg Score", f"{ir.average_score:.1f}/10", ir.readiness_label), unsafe_allow_html=True)
        with c3:
            trend_labels = {"improving": "Improving", "declining": "Declining", "stable": "Stable", "insufficient_data": "—"}
            st.markdown(cards.metric_card("Trend", trend_labels.get(ir.recent_trend, "—"), "vs. previous sessions"), unsafe_allow_html=True)
