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
from html import escape

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
            '<div class="brand"><div class="brand-mark">IP</div>'
            '<div class="brand-name">Interview Prep</div></div>'
            f'<div class="brand-sub">v{escape(settings.app.app_version)} &middot; AI-powered</div>',
            unsafe_allow_html=True,
        )

        # Document status indicator
        if session_state.is_ready():
            resume = session_state.get_resume()
            jd = session_state.get_jd()
            st.markdown(
                '<div class="status-box ready">'
                f'<span class="k">Resume</span>{escape((resume.file_name or "Resume")[:26])}'
                f'<span class="k" style="margin-top:.4rem">Target role</span>'
                f'{escape((jd.job_title or "Job Description")[:26])}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-box pending">'
                '<span class="k">No documents yet</span>'
                'Upload a resume and job description to begin.</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)

        pages = [
            ("upload",      "Upload Documents", ":material/upload_file:"),
            ("dashboard",   "Dashboard",        ":material/dashboard:"),
            ("chat",        "AI Assistant",     ":material/chat:"),
            ("ats",         "ATS Report",       ":material/fact_check:"),
            ("skill_gap",   "Skill Gap",        ":material/target:"),
            ("improvement", "Resume Tips",      ":material/edit_note:"),
            ("mock",        "Mock Interview",   ":material/mic:"),
            ("analytics",   "Analytics",        ":material/monitoring:"),
        ]

        for key, label, nav_icon in pages:
            active = session_state.get_active_page() == key
            if st.button(
                label,
                icon=nav_icon,
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                session_state.set_active_page(key)
                st.rerun()

        # ── Footer ─────────────────────────────────────────────────
        st.markdown(
            '<div class="sidebar-foot">Groq &middot; GPT-OSS 120B &middot; LangChain<br>'
            'ChromaDB &middot; Sentence Transformers</div>',
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

    module_path = page_map.get(page, "app.pages.upload_page")

    import importlib
    module = importlib.import_module(module_path)
    module.render()

    logger.debug("Page rendered", extra={"page": page})


if __name__ == "__main__":
    main()
