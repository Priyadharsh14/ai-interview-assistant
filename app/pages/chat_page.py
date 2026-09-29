"""RAG Chat page — chat with your resume and JD."""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory


def _render_message(role: str, content: str, sources: list[str] | None = None) -> None:
    """Render one turn with native chat styling so LLM markdown displays properly."""
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(content)
        if sources:
            st.caption("Sources: " + ", ".join(sources))


def render() -> None:
    st.markdown(
        cards.page_header(
            "AI assistant",
            "Ask questions about your resume and the job. Answers are drawn from your documents.",
            kicker="Chat",
        ),
        unsafe_allow_html=True,
    )

    if not session_state.is_ready():
        st.markdown(
            cards.empty_state("Upload documents first",
                              "The assistant needs your resume and JD to answer questions."),
            unsafe_allow_html=True,
        )
        return

    session_id = session_state.get_session_id()
    memory = session_state.get_memory()
    rag = service_factory.get_rag_service(session_id)

    # ── Mode selector ──────────────────────────────────────────────
    mode_map = {"Resume + JD": "both", "Resume only": "resume", "JD only": "jd"}
    mode_label = st.selectbox(
        "Search documents",
        list(mode_map.keys()),
        key="chat_mode_select",
        label_visibility="collapsed",
    )
    mode = mode_map[mode_label]
    ctx_type = "resume_chat" if mode == "resume" else "jd_chat" if mode == "jd" else "general"

    # ── Conversation history ───────────────────────────────────────
    history = memory.get_full_history(session_id, ctx_type)
    if not history.messages:
        st.caption(
            "Try: “Which of my projects show RAG experience?” · "
            "“What skills does this role require that I’m missing?”"
        )
    for msg in history.messages:
        _render_message(msg.role, msg.content, msg.sources or None)

    # ── Chat input ─────────────────────────────────────────────────
    user_input = st.chat_input("Ask anything about your resume or the job...")

    if user_input:
        _render_message("user", user_input)

        with st.spinner("Thinking…"):
            try:
                prior = memory.get_recent_history(session_id, ctx_type)
                response = rag.query(
                    question=user_input,
                    mode=mode,
                    conversation_history=prior,
                )
                sources = [
                    r.metadata.get("source_file", "document")
                    for r in response.sources
                ]
                memory.add_turn(
                    session_id, ctx_type,
                    user_message=user_input,
                    assistant_message=response.answer,
                    sources=list(dict.fromkeys(sources)),
                )
                _render_message(
                    "assistant", response.answer,
                    list(dict.fromkeys(sources)) if sources else None,
                )
                if not response.is_grounded:
                    st.caption("No relevant document chunks found — answer based on general knowledge.")
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Clear button ───────────────────────────────────────────────
    if history.messages:
        if st.button("Clear chat", key="clear_chat"):
            memory.clear_session(session_id, ctx_type)
            st.rerun()
