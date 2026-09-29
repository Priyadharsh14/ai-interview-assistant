"""ATS Report page — detailed keyword and score breakdown."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory


def render() -> None:
    st.markdown(
        cards.page_header(
            "ATS report",
            "How well your resume matches the keywords and requirements in the job description.",
            kicker="Analysis",
        ),
        unsafe_allow_html=True,
    )

    if not session_state.is_ready():
        st.markdown(
            cards.empty_state("No documents loaded",
                              "Upload your resume and JD first."),
            unsafe_allow_html=True,
        )
        return

    ats = session_state.get_ats_result()

    if ats is None:
        if st.button("Generate ATS Report", type="primary", use_container_width=True):
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
            cards.gauge(ats.overall_score, "ATS match score", ats.score_label, colour,
                        display=f"{ats.overall_score:.0f}%"),
            unsafe_allow_html=True,
        )

    with c_breakdown:
        bd = ats.breakdown
        rows = "".join(
            cards.bar_row(label, score)
            for label, score in [
                ("Keyword match", bd.keyword_match_score),
                ("Skills match", bd.skills_match_score),
                ("Experience match", bd.experience_match_score),
                ("Education match", bd.education_match_score),
            ]
        )
        st.markdown(
            '<div class="panel pad-lg"><div class="card-title">Score breakdown</div>'
            f"{rows}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Keywords ───────────────────────────────────────────────────
    k_matched, k_missing = st.columns(2, gap="large")

    with k_matched:
        st.markdown(cards.section_header("Matched Keywords", sub=True), unsafe_allow_html=True)
        st.markdown(
            cards.skill_pills(ats.matched_keywords, "matched"),
            unsafe_allow_html=True,
        )

    with k_missing:
        st.markdown(cards.section_header("Missing Keywords", sub=True), unsafe_allow_html=True)
        st.markdown(
            cards.skill_pills(ats.missing_keywords, "missing"),
            unsafe_allow_html=True,
        )

    # ── Recommendations ────────────────────────────────────────────
    if ats.recommendations:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Recommendations", sub=True), unsafe_allow_html=True)
        for rec in ats.recommendations:
            st.markdown(cards.recommendation(rec), unsafe_allow_html=True)
