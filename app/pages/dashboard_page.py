"""Dashboard page — overview cards and quick-launch analysis."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory


def render() -> None:
    resume = session_state.get_resume()
    jd = session_state.get_jd()

    if not session_state.is_ready():
        st.markdown(
            cards.empty_state(
                "🎯",
                "Upload your documents to begin",
                "Add your resume and a job description using the Upload tab in the sidebar.",
            ),
            unsafe_allow_html=True,
        )
        return

    # ── Candidate header ───────────────────────────────────────────
    name = (resume.contact.name or "Candidate") if resume else "Candidate"
    title = jd.job_title or "Target Role" if jd else "Target Role"
    st.markdown(
        f'<h2 style="color:var(--text-primary);margin-bottom:.25rem">'
        f'Welcome, {name}</h2>'
        f'<p style="color:var(--text-secondary)">Preparing for: <strong>{title}</strong></p>',
        unsafe_allow_html=True,
    )

    # ── Run analysis button ────────────────────────────────────────
    if st.button("🔍 Run Full Analysis", use_container_width=True):
        _run_analysis(resume, jd)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Dashboard cards ────────────────────────────────────────────
    analytics = session_state.get_analytics()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if analytics and analytics.has_ats_data:
            score = analytics.ats.overall_score
            colour = _score_colour_class(score)
            st.markdown(
                cards.metric_card("ATS Score", f"{score:.0f}%",
                                  analytics.ats.score_label, colour),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                cards.metric_card("ATS Score", "—", "Run analysis first"),
                unsafe_allow_html=True,
            )

    with col2:
        if analytics and analytics.has_resume_data:
            score = analytics.resume_strength.strength_score
            colour = _score_colour_class(score)
            st.markdown(
                cards.metric_card("Resume Strength", f"{score:.0f}%",
                                  analytics.resume_strength.strength_label, colour),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                cards.metric_card("Resume Strength", "—", "Run analysis first"),
                unsafe_allow_html=True,
            )

    with col3:
        if analytics and analytics.has_skills_data:
            missing = analytics.skills.total_missing
            colour = "green" if missing == 0 else "amber" if missing < 4 else "red"
            st.markdown(
                cards.metric_card("Missing Skills", str(missing),
                                  f"{analytics.skills.skill_match_percentage:.0f}% matched",
                                  colour),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                cards.metric_card("Missing Skills", "—", "Run analysis first"),
                unsafe_allow_html=True,
            )

    with col4:
        if analytics and analytics.has_interview_data:
            score = analytics.interview_readiness.readiness_score
            colour = _score_colour_class(score)
            st.markdown(
                cards.metric_card("Interview Readiness", f"{score:.0f}%",
                                  analytics.interview_readiness.readiness_label, colour),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                cards.metric_card("Interview Readiness", "—", "Complete a mock interview"),
                unsafe_allow_html=True,
            )

    # ── Quick stats ────────────────────────────────────────────────
    if resume and jd:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Document Summary"), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Resume:** {resume.file_name} · {resume.word_count} words")
            if resume.skills:
                st.markdown(
                    cards.skill_pills(resume.skills[:8], "matched"),
                    unsafe_allow_html=True,
                )
        with c2:
            st.markdown(f"**JD:** {jd.job_title or 'Job Description'} · {jd.word_count} words")
            if jd.required_skills:
                st.markdown(
                    cards.skill_pills(jd.required_skills[:8]),
                    unsafe_allow_html=True,
                )


def _run_analysis(resume, jd) -> None:
    """Run ATS, skill gap, and improvement analysis, update analytics."""
    with st.spinner("Running analysis…"):
        try:
            ats = service_factory.get_ats_engine().score(resume, jd)
            session_state.set_ats_result(ats)

            gap = service_factory.get_skill_gap_engine().analyse(resume, jd)
            session_state.set_skill_gap(gap)

            imp = service_factory.get_improvement_engine().improve(resume, jd)
            session_state.set_improvement(imp)

            report = service_factory.get_analytics_service().generate_report(
                ats_result=ats,
                skill_gap_result=gap,
                improvement_report=imp,
                mock_sessions=[session_state.get_mock_session()]
                if session_state.get_mock_session() else None,
            )
            session_state.set_analytics(report)
            st.success("Analysis complete!")
            st.rerun()
        except Exception as e:
            st.error(f"Analysis failed: {e}")


def _score_colour_class(score: float) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "blue"
    if score >= 40:
        return "amber"
    return "red"
