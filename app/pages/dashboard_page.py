"""Dashboard page — overview, headline scores, and next steps."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory


def render() -> None:
    resume = session_state.get_resume()
    jd = session_state.get_jd()

    if not session_state.is_ready():
        st.markdown(
            cards.page_header(
                "Dashboard",
                "Your readiness at a glance, once your documents are loaded.",
                kicker="Overview",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            cards.steps([
                ("Upload documents", "Add your resume and the job description.", "current"),
                ("Run the analysis", "Get your ATS score and skill gaps.", "todo"),
                ("Practise interviews", "Answer tailored questions and get scored.", "todo"),
            ]),
            unsafe_allow_html=True,
        )
        st.markdown(
            cards.empty_state(
                "Nothing to show yet",
                "Open Upload Documents in the sidebar to add your resume and a job description.",
                icon_name="upload",
            ),
            unsafe_allow_html=True,
        )
        return

    analytics = session_state.get_analytics()

    # ── Hero ───────────────────────────────────────────────────────
    name = (resume.contact.name or "Candidate") if resume else "Candidate"
    title = (jd.job_title or "Target Role") if jd else "Target Role"
    chips = [
        f"{resume.word_count} words in resume",
        f"{len(resume.skills)} skills detected",
        f"{len(jd.required_skills)} required skills in job",
    ]
    st.markdown(cards.hero(name, title, chips), unsafe_allow_html=True)

    label = "Re-run analysis" if analytics else "Run full analysis"
    if st.button(label, type="primary"):
        _run_analysis(resume, jd)

    st.markdown("<div style='height:.75rem'></div>", unsafe_allow_html=True)

    # ── Headline gauges ────────────────────────────────────────────
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        if analytics and analytics.has_ats_data:
            s = analytics.ats.overall_score
            st.markdown(cards.gauge(s, "ATS match", analytics.ats.score_label,
                                    _score_colour_class(s)), unsafe_allow_html=True)
        else:
            st.markdown(cards.gauge(0, "ATS match", "Run the analysis", display="--"),
                        unsafe_allow_html=True)
    with g2:
        if analytics and analytics.has_resume_data:
            s = analytics.resume_strength.strength_score
            st.markdown(cards.gauge(s, "Resume strength", analytics.resume_strength.strength_label,
                                    _score_colour_class(s)), unsafe_allow_html=True)
        else:
            st.markdown(cards.gauge(0, "Resume strength", "Run the analysis", display="--"),
                        unsafe_allow_html=True)
    with g3:
        if analytics and analytics.has_skills_data:
            s = analytics.skills.skill_match_percentage
            st.markdown(
                cards.gauge(s, "Skill match", f"{analytics.skills.total_missing} skills missing",
                            _score_colour_class(s)),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(cards.gauge(0, "Skill match", "Run the analysis", display="--"),
                        unsafe_allow_html=True)
    with g4:
        if analytics and analytics.has_interview_data:
            s = analytics.interview_readiness.readiness_score
            st.markdown(cards.gauge(s, "Interview readiness",
                                    analytics.interview_readiness.readiness_label,
                                    _score_colour_class(s)), unsafe_allow_html=True)
        else:
            st.markdown(cards.gauge(0, "Interview readiness", "Complete a mock interview",
                                    display="--"), unsafe_allow_html=True)

    # ── Next steps ─────────────────────────────────────────────────
    analysed = bool(analytics and analytics.has_ats_data)
    practised = bool(analytics and analytics.has_interview_data)
    st.markdown(cards.section_header("Next steps", sub=True), unsafe_allow_html=True)
    st.markdown(
        cards.steps([
            ("Documents loaded", f"{resume.file_name or 'Resume'} and {title}.", "done"),
            ("Run the analysis",
             "ATS score, skill gaps and resume tips are ready." if analysed
             else "Use the button above to score your resume against the job.",
             "done" if analysed else "current"),
            ("Practise interviews",
             "Mock interview completed." if practised
             else "Open Mock Interview in the sidebar to get tailored questions.",
             "done" if practised else ("current" if analysed else "todo")),
        ]),
        unsafe_allow_html=True,
    )

    # ── Skills snapshot ────────────────────────────────────────────
    st.markdown(cards.section_header("Skills snapshot", sub=True), unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown('<div class="card-title">Strongest skills on your resume</div>',
                    unsafe_allow_html=True)
        st.markdown(cards.skill_pills(resume.skills[:12], "matched"), unsafe_allow_html=True)
    with c2:
        gap = session_state.get_skill_gap()
        if gap and gap.missing_technical_skills:
            st.markdown('<div class="card-title">Biggest gaps for this role</div>',
                        unsafe_allow_html=True)
            st.markdown(cards.skill_pills(gap.missing_technical_skills[:12], "missing"),
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="card-title">What the role asks for</div>',
                        unsafe_allow_html=True)
            st.markdown(cards.skill_pills(jd.required_skills[:12]), unsafe_allow_html=True)


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
