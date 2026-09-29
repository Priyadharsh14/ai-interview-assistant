"""Skill Gap Analysis page."""

from __future__ import annotations
import streamlit as st
from app.components import cards, session_state, service_factory

def render() -> None:
    st.markdown(
        cards.page_header(
            "Skill gap",
            "The skills this job asks for, split into what you already show and what is missing.",
            kicker="Analysis",
        ),
        unsafe_allow_html=True,
    )
    if not session_state.is_ready():
        st.markdown(cards.empty_state("Upload documents first", "Add your resume and a job description on the Upload Documents page."), unsafe_allow_html=True)
        return

    gap = session_state.get_skill_gap()
    if gap is None:
        if st.button("Analyse Skill Gap", type="primary", use_container_width=True):
            with st.spinner("Analysing skills…"):
                gap = service_factory.get_skill_gap_engine().analyse(
                    session_state.get_resume(), session_state.get_jd()
                )
                session_state.set_skill_gap(gap)
                st.rerun()
        return

    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        colour = "green" if gap.skill_match_percentage >= 80 else "amber" if gap.skill_match_percentage >= 50 else "red"
        st.markdown(
            cards.gauge(gap.skill_match_percentage, "Skill match",
                        f"{len(gap.matched_skills)} matched, "
                        f"{len(gap.missing_technical_skills) + len(gap.missing_soft_skills)} missing",
                        colour),
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(cards.section_header("Matched Skills", sub=True), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.matched_skills, "matched"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_tech, col_soft = st.columns(2)
    with col_tech:
        st.markdown(cards.section_header("Missing Technical Skills", sub=True), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.missing_technical_skills, "missing"), unsafe_allow_html=True)
    with col_soft:
        st.markdown(cards.section_header("Missing Soft Skills", sub=True), unsafe_allow_html=True)
        st.markdown(cards.skill_pills(gap.missing_soft_skills, "missing"), unsafe_allow_html=True)

    if gap.learning_recommendations:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Learning Recommendations", sub=True), unsafe_allow_html=True)
        for rec in gap.learning_recommendations:
            st.markdown(cards.recommendation(rec), unsafe_allow_html=True)
