"""Skill Gap Analysis page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def render() -> None:
    st.markdown(cards.section_header("🧠 Skill Gap Analysis"), unsafe_allow_html=True)
    if not session_state.is_ready():
        st.markdown(cards.empty_state("🧠","Upload documents first",""), unsafe_allow_html=True)
        return

    gap = session_state.get_skill_gap()
    if gap is None:
        if st.button("Analyse Skill Gap", use_container_width=True):
            with st.spinner("Analysing skills…"):
                gap = service_factory.get_skill_gap_engine().analyse(
                    session_state.get_resume(), session_state.get_jd()
                )
                session_state.set_skill_gap(gap)
                st.rerun()
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        colour = "green" if gap.skill_match_percentage >= 80 else "amber" if gap.skill_match_percentage >= 50 else "red"
        st.markdown(cards.metric_card("Skill Match", f"{gap.skill_match_percentage:.0f}%",
                                      f"{len(gap.matched_skills)} skills matched", colour), unsafe_allow_html=True)

    with c2:
        st.markdown(cards.section_header("Matched Skills"), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.matched_skills, "matched"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_tech, col_soft = st.columns(2)
    with col_tech:
        st.markdown(cards.section_header("❌ Missing Technical Skills"), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.missing_technical_skills, "missing"), unsafe_allow_html=True)
    with col_soft:
        st.markdown(cards.section_header("❌ Missing Soft Skills"), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.missing_soft_skills, "missing"), unsafe_allow_html=True)

    if gap.learning_recommendations:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("📚 Learning Recommendations"), unsafe_allow_html=True)
        for rec in gap.learning_recommendations:
            st.markdown(f'<div style="background:var(--bg-card);border:1px solid var(--border-soft);border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;color:var(--text-secondary);font-size:.88rem">→ {rec}</div>', unsafe_allow_html=True)
