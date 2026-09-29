"""
Upload Page — Resume and Job Description intake.

Handles file upload (PDF/DOCX) and text paste for JD.
Runs the full parse + index pipeline on submission.
"""

from __future__ import annotations

import streamlit as st

from app.components import cards, session_state, service_factory
from config.logging_config import get_logger

logger = get_logger(__name__)


def render() -> None:
    st.markdown(
        cards.page_header(
            "Upload documents",
            "Add your resume and the job you are targeting. Everything else in the app is "
            "built from these two documents.",
            kicker="Step 1 of 3",
        ),
        unsafe_allow_html=True,
    )
    loaded = session_state.is_ready()
    st.markdown(
        cards.steps([
            ("Upload documents", "Resume as PDF or DOCX, plus the job description.",
             "done" if loaded else "current"),
            ("Run the analysis", "ATS score, skill gaps and resume tips.",
             "current" if loaded else "todo"),
            ("Practise interviews", "Tailored questions with scored feedback.", "todo"),
        ]),
        unsafe_allow_html=True,
    )

    col_resume, col_jd = st.columns(2, gap="large")

    # ── Resume upload ──────────────────────────────────────────────
    with col_resume:
        st.markdown('<div class="card-title">Your resume</div>', unsafe_allow_html=True)
        st.markdown('<p class="card-note">PDF or DOCX, up to 10 MB.</p>', unsafe_allow_html=True)
        resume_file = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx"],
            key="resume_uploader",
            label_visibility="collapsed",
        )

    # ── JD input ───────────────────────────────────────────────────
    with col_jd:
        st.markdown('<div class="card-title">Job description</div>', unsafe_allow_html=True)
        st.markdown('<p class="card-note">Upload the posting or paste its text.</p>',
                    unsafe_allow_html=True)
        jd_tab_file, jd_tab_text = st.tabs(["Upload file", "Paste text"])

        with jd_tab_file:
            jd_file = st.file_uploader(
                "Upload JD",
                type=["pdf", "docx"],
                key="jd_uploader",
                label_visibility="collapsed",
            )
        with jd_tab_text:
            jd_text = st.text_area(
                "Paste job description",
                height=200,
                placeholder="Paste the full job description here...",
                label_visibility="collapsed",
                key="jd_text_input",
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Process button ─────────────────────────────────────────────
    has_resume = resume_file is not None
    has_jd = jd_file is not None or (jd_text and jd_text.strip())

    if not has_resume or not has_jd:
        st.info("Upload a resume and provide a job description to continue.")
        return

    if st.button("Analyse Resume & JD →", type="primary", use_container_width=True):
        _run_pipeline(resume_file, jd_file, jd_text)


def _run_pipeline(resume_file, jd_file, jd_text: str) -> None:
    """Run the full parse + index pipeline with progress feedback."""
    doc_svc = service_factory.get_document_processing_service()
    resume_svc = service_factory.get_resume_parser()
    jd_svc = service_factory.get_jd_service()
    indexer = service_factory.get_document_indexer()
    session_id = session_state.get_session_id()

    progress = st.progress(0, text="Starting…")

    try:
        # ── 1. Save and extract resume ─────────────────────────────
        progress.progress(10, text="Extracting resume text…")
        import tempfile, os
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{resume_file.name.rsplit('.',1)[-1]}"
        ) as tmp:
            tmp.write(resume_file.read())
            tmp_path = tmp.name

        extracted_resume = doc_svc.process(tmp_path, resume_file.name)
        os.unlink(tmp_path)

        # ── 2. Parse resume ────────────────────────────────────────
        progress.progress(25, text="Parsing resume structure…")
        resume = resume_svc.parse(extracted_resume)
        session_state.set_resume(resume)

        # ── 3. Process JD ──────────────────────────────────────────
        progress.progress(45, text="Processing job description…")
        if jd_file:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{jd_file.name.rsplit('.',1)[-1]}"
            ) as tmp:
                tmp.write(jd_file.read())
                tmp_jd_path = tmp.name
            extracted_jd = doc_svc.process(tmp_jd_path, jd_file.name)
            os.unlink(tmp_jd_path)
            jd = jd_svc.process_document(extracted_jd)
        else:
            jd = jd_svc.process_text(jd_text)
        session_state.set_jd(jd)

        # ── 4. Index both documents ────────────────────────────────
        progress.progress(65, text="Building search index…")
        indexer.index_resume(resume, session_id)
        indexer.index_jd(jd, session_id)

        # ── 5. Clear stale analysis results ───────────────────────
        session_state.reset_analysis()

        progress.progress(100, text="Done!")
        st.success(
            f"Resume and JD loaded. "
            f"Detected **{len(resume.skills)} skills** and "
            f"**{len(jd.required_skills)} required skills**."
        )

    except Exception as e:
        logger.error("Upload pipeline failed", extra={"error": str(e)})
        progress.empty()
        st.error(f"Processing failed: {e}")
