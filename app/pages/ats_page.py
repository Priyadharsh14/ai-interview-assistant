"""ATS Report page — detailed keyword and score breakdown."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory


def render() -> None:
    st.markdown(cards.section_header("📊 ATS Report"), unsafe_allow_html=True)

    if not session_state.is_ready():
        st.markdown(
            cards.empty_state("📊", "No documents loaded",
                              "Upload your resume and JD first."),
            unsafe_allow_html=True,
        )
        return

    ats = session_state.get_ats_result()

    if ats is None:
        if st.button("Generate ATS Report", use_container_width=True):
            with st.spinner("Scoring resume against JD…"):
                resume = session_state.get_resume()
                jd = session_state.get_jd()
                ats = service_factory.get_ats_engine().score(resume, jd)
                session_state.set_ats_result(ats)
                st.rerun()
        return

    # ── Overall score + breakdown ──────────────────────────────────
    c_score, c_breakdown = st.columns([1, 2], gap="large")

    with c_score:
        colour = ("green" if ats.overall_score >= 80 else
                  "blue" if ats.overall_score >= 60 else
                  "amber" if ats.overall_score >= 40 else "red")
        st.markdown(
            cards.metric_card("ATS Match Score",
                              f"{ats.overall_score:.1f}%",
                              ats.score_label, colour),
            unsafe_allow_html=True,
        )

    with c_breakdown:
        st.markdown(cards.section_header("Score Breakdown"), unsafe_allow_html=True)
        bd = ats.breakdown
        for label, score in [
            ("Keyword Match", bd.keyword_match_score),
            ("Skills Match", bd.skills_match_score),
            ("Experience Match", bd.experience_match_score),
            ("Education Match", bd.education_match_score),
        ]:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'margin-bottom:.3rem"><span style="color:var(--text-secondary);'
                f'font-size:.85rem">{label}</span>'
                f'<span style="color:var(--text-primary);font-weight:600">'
                f'{score:.0f}%</span></div>',
                unsafe_allow_html=True,
            )
            st.progress(score / 100)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Keywords ───────────────────────────────────────────────────
    k_matched, k_missing = st.columns(2, gap="large")

    with k_matched:
        st.markdown(cards.section_header("✅ Matched Keywords"), unsafe_allow_html=True)
        st.markdown(
            cards.skill_pills(ats.matched_keywords, "matched"),
            unsafe_allow_html=True,
        )

    with k_missing:
        st.markdown(cards.section_header("❌ Missing Keywords"), unsafe_allow_html=True)
        st.markdown(
            cards.skill_pills(ats.missing_keywords, "missing"),
            unsafe_allow_html=True,
        )

    # ── Recommendations ────────────────────────────────────────────
    if ats.recommendations:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("💡 Recommendations"), unsafe_allow_html=True)
        for rec in ats.recommendations:
            st.markdown(
                f'<div style="background:var(--bg-card);border:1px solid var(--border-soft);'
                f'border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;'
                f'color:var(--text-secondary);font-size:.88rem">→ {rec}</div>',
                unsafe_allow_html=True,
            )
