"""Analytics page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def render() -> None:
    st.markdown(cards.section_header("📈 Analytics"), unsafe_allow_html=True)
    analytics = session_state.get_analytics()

    if analytics is None:
        if not session_state.is_ready():
            st.markdown(cards.empty_state("📈","Upload documents first",""), unsafe_allow_html=True)
            return
        if st.button("Generate Analytics Report", use_container_width=True):
            with st.spinner("Building report…"):
                report = service_factory.get_analytics_service().generate_report(
                    ats_result=session_state.get_ats_result(),
                    skill_gap_result=session_state.get_skill_gap(),
                    improvement_report=session_state.get_improvement(),
                    mock_sessions=[session_state.get_mock_session()] if session_state.get_mock_session() else None,
                )
                session_state.set_analytics(report)
                st.rerun()
        return

    overall = analytics.overall_readiness_score
    colour = "green" if overall >= 80 else "blue" if overall >= 60 else "amber" if overall >= 40 else "red"
    st.markdown(cards.metric_card("Overall Readiness", f"{overall:.0f}%", "Composite score", colour), unsafe_allow_html=True)

    if analytics.has_interview_data:
        ir = analytics.interview_readiness
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Interview Performance"), unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(cards.metric_card("Sessions Done", str(ir.sessions_completed), ""), unsafe_allow_html=True)
        with c2:
            st.markdown(cards.metric_card("Avg Score", f"{ir.average_score:.1f}/10", ir.readiness_label), unsafe_allow_html=True)
        with c3:
            trend_icons = {"improving": "📈", "declining": "📉", "stable": "➡️", "insufficient_data": "—"}
            st.markdown(cards.metric_card("Trend", trend_icons.get(ir.recent_trend,"—"), ir.recent_trend.replace("_"," ").title()), unsafe_allow_html=True)
