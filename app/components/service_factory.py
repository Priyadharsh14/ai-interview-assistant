"""
Service Factory.

Constructs all backend services with their dependencies and caches
them in Streamlit session state. Each service is built once per session.

Using @st.cache_resource for LLM and embedder (expensive to initialise).
Using session state for stateful services (tied to one user's session).
"""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings


@st.cache_resource(show_spinner="Loading AI model...")
def _get_llm_provider():
    """Groq LLM provider — loaded once per Streamlit server process."""
    from infrastructure.llm.groq_provider import GroqProvider
    return GroqProvider()


@st.cache_resource(show_spinner="Loading embedding model...")
def _get_embedder():
    """Sentence transformer embedder — loaded once, model cached on disk."""
    from infrastructure.embeddings.sentence_transformer_embedder import (
        SentenceTransformerEmbedder,
    )
    return SentenceTransformerEmbedder()


@st.cache_resource
def _get_vector_store():
    """ChromaDB repository — single persistent client per process."""
    from infrastructure.vector_store.chroma_repository import ChromaRepository
    return ChromaRepository()


def get_document_processing_service():
    from core.services.document_processing_service import DocumentProcessingService
    return DocumentProcessingService()


def get_resume_parser():
    from core.services.resume_parser_service import ResumeParserService
    return ResumeParserService(llm=_get_llm_provider())


def get_jd_service():
    from core.services.jd_processing_service import JDProcessingService
    return JDProcessingService(llm=_get_llm_provider())


def get_embedding_pipeline():
    from core.services.embedding_pipeline import EmbeddingPipeline
    from infrastructure.embeddings.document_chunker import DocumentChunker
    return EmbeddingPipeline(
        embedder=_get_embedder(),
        chunker=DocumentChunker.from_settings(),
    )


def get_document_indexer():
    from core.services.document_indexer import DocumentIndexer
    return DocumentIndexer(
        embedding_pipeline=get_embedding_pipeline(),
        vector_store=_get_vector_store(),
    )


def get_rag_service(session_id: str):
    from core.services.rag_service import RAGService
    return RAGService(
        llm=_get_llm_provider(),
        embedder=_get_embedder(),
        vector_store=_get_vector_store(),
        session_id=session_id,
    )


def get_ats_engine():
    from core.services.ats_engine import ATSEngine
    return ATSEngine(llm=_get_llm_provider())


def get_skill_gap_engine():
    from core.services.skill_gap_engine import SkillGapEngine
    return SkillGapEngine(llm=_get_llm_provider())


def get_improvement_engine():
    from core.services.resume_improvement_engine import ResumeImprovementEngine
    return ResumeImprovementEngine(llm=_get_llm_provider())


def get_question_generator():
    from core.services.question_generator import QuestionGenerator
    return QuestionGenerator(llm=_get_llm_provider())


def get_answer_generator():
    from core.services.answer_generator import AnswerGenerator
    return AnswerGenerator(llm=_get_llm_provider())


def get_mock_interview_service():
    from core.services.mock_interview_service import MockInterviewService
    return MockInterviewService(
        question_generator=get_question_generator(),
        answer_generator=get_answer_generator(),
    )


def get_analytics_service():
    from core.services.analytics_service import AnalyticsService
    return AnalyticsService()
