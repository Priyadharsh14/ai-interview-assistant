"""Mock Interview page — interactive question-answer session."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory
from core.services.mock_interview_service import InterviewScorecard


def render() -> None:
    st.markdown(cards.section_header("🎤 Mock Interview"), unsafe_allow_html=True)

    if not session_state.is_ready():
        st.markdown(
            cards.empty_state("🎤", "Upload documents first",
                              "A mock interview needs your resume and JD."),
            unsafe_allow_html=True,
        )
        return

    session = session_state.get_mock_session()

    # ── Start new session ──────────────────────────────────────────
    if session is None:
        _render_start_screen()
        return

    # ── Session complete ───────────────────────────────────────────
    if session.is_complete:
        _render_scorecard(session)
        return

    # ── Active session ─────────────────────────────────────────────
    _render_active_session(session)


def _render_start_screen() -> None:
    st.markdown(
        '<p style="color:var(--text-secondary)">Choose how many questions '
        "for your mock interview session.</p>",
        unsafe_allow_html=True,
    )
    num_q = st.slider("Number of questions", 5, 15, 10)
    if st.button("Start Mock Interview →", use_container_width=True):
        with st.spinner("Generating questions…"):
            try:
                svc = service_factory.get_mock_interview_service()
                session = svc.start_session(
                    resume=session_state.get_resume(),
                    jd=session_state.get_jd(),
                    num_questions=num_q,
                )
                session_state.set_mock_session(session)
                st.rerun()
            except Exception as e:
                st.error(f"Could not start session: {e}")


def _render_active_session(session) -> None:
    svc = service_factory.get_mock_interview_service()
    total = len(session.questions)
    answered = session.questions_answered

    # Progress bar
    st.progress(answered / total, text=f"Question {answered + 1} of {total}")
    st.markdown("<br>", unsafe_allow_html=True)

    current_q = svc.get_next_question(session)
    if current_q is None:
        return

    # Question display
    type_badge = (
        f'<span style="background:var(--accent-soft);color:var(--accent);'
        f'border-radius:999px;padding:.2rem .6rem;font-size:.72rem;font-weight:600">'
        f'{current_q.question_type.value.upper()}</span>'
    )
    diff_colours = {"easy": "#22c55e", "medium": "#f59e0b", "hard": "#ef4444"}
    diff_colour = diff_colours.get(current_q.difficulty.value, "#94a3b8")
    diff_badge = (
        f'<span style="color:{diff_colour};font-size:.75rem;font-weight:600">'
        f'◆ {current_q.difficulty.value.upper()}</span>'
    )

    st.markdown(
        f'<div style="background:var(--bg-card);border:1px solid var(--border-soft);'
        f'border-radius:12px;padding:1.5rem">'
        f'<div style="margin-bottom:.75rem">{type_badge}&nbsp;&nbsp;{diff_badge}</div>'
        f'<p style="font-size:1.05rem;color:var(--text-primary);font-weight:500;'
        f'line-height:1.6">{current_q.question}</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    answer_text = st.text_area(
        "Your answer", height=150,
        placeholder="Type your answer here…",
        key=f"answer_{current_q.question_id}",
        label_visibility="collapsed",
    )

    col_submit, col_skip, col_end = st.columns([3, 1, 1])
    with col_submit:
        if st.button("Submit Answer →", use_container_width=True,
                     disabled=not answer_text.strip()):
            with st.spinner("Evaluating…"):
                updated, evaluation = svc.submit_answer(
                    session, answer_text,
                    resume=session_state.get_resume(),
                    jd=session_state.get_jd(),
                )
                session_state.set_mock_session(updated)
                _show_evaluation(evaluation, current_q.model_answer or "")
                st.rerun()
    with col_skip:
        if st.button("Skip", use_container_width=True):
            updated = svc.skip_question(session)
            session_state.set_mock_session(updated)
            st.rerun()
    with col_end:
        if st.button("End", use_container_width=True):
            scorecard = svc.end_session(session)
            session_state.set_mock_session(session)
            st.rerun()


def _show_evaluation(evaluation, model_answer: str) -> None:
    score = evaluation.score
    colour = "#22c55e" if score >= 7 else "#f59e0b" if score >= 5 else "#ef4444"
    st.markdown(
        f'<div style="background:var(--bg-card);border:1px solid var(--border-soft);'
        f'border-radius:10px;padding:1rem;margin-top:.75rem">'
        f'<div style="color:{colour};font-size:1.4rem;font-weight:700">'
        f'{score:.1f} / 10</div>'
        f'<p style="color:var(--text-secondary);font-size:.88rem;margin:.5rem 0">'
        f'{evaluation.feedback}</p></div>',
        unsafe_allow_html=True,
    )


def _render_scorecard(session) -> None:
    svc = service_factory.get_mock_interview_service()
    scorecard: InterviewScorecard = svc._generate_scorecard(session)

    st.markdown(cards.section_header("🏆 Interview Complete"), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        colour = "green" if scorecard.overall_score >= 7 else "amber" if scorecard.overall_score >= 5 else "red"
        st.markdown(
            cards.metric_card("Overall Score",
                              f"{scorecard.overall_score:.1f}/10",
                              scorecard.overall_band, colour),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            cards.metric_card("Answered",
                              str(scorecard.answered_questions),
                              f"of {scorecard.total_questions} questions"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            cards.metric_card("Duration",
                              f"{scorecard.duration_minutes:.0f} min",
                              f"{scorecard.completion_rate:.0f}% completion"),
            unsafe_allow_html=True,
        )

    # Category breakdown
    if scorecard.category_scores:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(cards.section_header("Category Scores"), unsafe_allow_html=True)
        for cat in scorecard.category_scores:
            col_name, col_score, col_bar = st.columns([3, 1, 4])
            with col_name:
                st.markdown(
                    f'<span style="color:var(--text-secondary);font-size:.88rem">'
                    f'{cat.category}</span>',
                    unsafe_allow_html=True,
                )
            with col_score:
                st.markdown(
                    f'<span style="font-weight:600">{cat.average_score:.1f}</span>',
                    unsafe_allow_html=True,
                )
            with col_bar:
                st.progress(cat.average_score / 10)

    # Restart
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Start New Interview", use_container_width=True):
        session_state.set_mock_session(None)
        st.rerun()
