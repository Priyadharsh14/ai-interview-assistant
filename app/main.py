"""
AI Interview Preparation Assistant — Application Entry Point.

Run locally:  streamlit run app/main.py
Run in Docker: CMD already set in Dockerfile

Bootstrap order:
    1. Settings loaded and validated (exits on misconfiguration)
    2. Logging configured (environment-aware format)
    3. Streamlit page config set
    4. Global CSS injected
    5. Session state initialised
    6. Sidebar navigation rendered
    7. Active page rendered
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.components import session_state
from app.styles.theme import get_global_css
from config.logging_config import configure_logging, get_logger
from config.settings import get_settings

# ── Bootstrap — runs once per Streamlit process ────────────────────
settings = get_settings()
configure_logging(
    level=settings.app.log_level,
    env=settings.app.app_env,
)
logger = get_logger(__name__)


def main() -> None:
    """Configure and launch the Streamlit application."""
    st.set_page_config(
        page_title=settings.app.app_name,
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": "https://github.com/yourusername/ai-interview-assistant",
            "Report a bug": "https://github.com/yourusername/ai-interview-assistant/issues",
            "About": f"### {settings.app.app_name}\nv{settings.app.app_version}",
        },
    )

    # Inject design system CSS
    st.markdown(get_global_css(), unsafe_allow_html=True)

    # Initialise all session state keys with safe defaults
    session_state.init_session()

    # ── Sidebar ────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<h2 style="color:var(--text-primary);margin:0;font-size:1.2rem">'
            '🎯 Interview Prep</h2>'
            '<p style="color:var(--text-muted);font-size:.72rem;margin:.2rem 0 1.5rem">'
            f'v{settings.app.app_version} · AI-powered</p>',
            unsafe_allow_html=True,
        )

        # Document status indicator
        if session_state.is_ready():
            resume = session_state.get_resume()
            jd = session_state.get_jd()
            st.markdown(
                f'<div style="background:rgba(34,197,94,.12);border:1px solid '
                f'rgba(34,197,94,.3);border-radius:8px;padding:.6rem .8rem;'
                f'margin-bottom:1rem;font-size:.78rem;color:#22c55e">'
                f'✅ {(resume.file_name or "Resume")[:22]}<br>'
                f'✅ {(jd.job_title or "Job Description")[:22]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:rgba(245,158,11,.10);border:1px solid '
                'rgba(245,158,11,.3);border-radius:8px;padding:.6rem .8rem;'
                'margin-bottom:1rem;font-size:.78rem;color:#f59e0b">'
                '⚠️ Upload documents to begin</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p style="color:var(--text-muted);font-size:.72rem;'
            'text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .4rem">'
            'Navigation</p>',
            unsafe_allow_html=True,
        )

        pages = [
            ("📁", "upload",      "Upload Documents"),
            ("🏠", "dashboard",   "Dashboard"),
            ("💬", "chat",        "AI Assistant"),
            ("📊", "ats",         "ATS Report"),
            ("🧠", "skill_gap",   "Skill Gap"),
            ("✏️", "improvement", "Resume Tips"),
            ("🎤", "mock",        "Mock Interview"),
            ("📈", "analytics",   "Analytics"),
        ]

        for icon, key, label in pages:
            active = session_state.get_active_page() == key
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                session_state.set_active_page(key)
                st.rerun()

        # ── Footer ─────────────────────────────────────────────────
        st.markdown("<br>" * 3, unsafe_allow_html=True)
        st.markdown(
            '<div style="color:var(--text-muted);font-size:.68rem;text-align:center">'
            f'Groq · Llama 3.3 · LangChain<br>'
            f'ChromaDB · Sentence Transformers</div>',
            unsafe_allow_html=True,
        )

    # ── Main content area ──────────────────────────────────────────
    page = session_state.get_active_page()

    page_map = {
        "upload":      "app.pages.upload_page",
        "dashboard":   "app.pages.dashboard_page",
        "chat":        "app.pages.chat_page",
        "ats":         "app.pages.ats_page",
        "skill_gap":   "app.pages.skill_gap_page",
        "improvement": "app.pages.improvement_page",
        "mock":        "app.pages.mock_interview_page",
        "analytics":   "app.pages.analytics_page",
    }

    module_path = page_map.get(page, "app.pages.dashboard_page")

    import importlib
    module = importlib.import_module(module_path)
    module.render()

    logger.debug("Page rendered", extra={"page": page})


if __name__ == "__main__":
    main()
