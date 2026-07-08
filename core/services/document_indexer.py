"""
Document Indexer Service.

Orchestrates the indexing workflow:
    ExtractedDocument / Resume / JobDescription
    → EmbeddingPipeline  (chunk + embed)
    → ChromaRepository   (store vectors)

This is the "write path" — called once when a user uploads a document.
The RAG service is the "read path" — called on every query.

Keeping indexing separate from querying ensures:
    - Documents are only embedded once (expensive operation)
    - Re-indexing a document cleanly replaces old chunks
    - The indexing step can be retried independently of queries
"""

from __future__ import annotations

from dataclasses import dataclass

from config.logging_config import get_logger
from core.domain.job_description import JobDescription
from core.domain.resume import Resume
from core.interfaces.document_processor import ExtractedDocument
from core.interfaces.vector_store import BaseVectorStore
from core.services.embedding_pipeline import EmbeddingPipeline
from infrastructure.vector_store.collection_names import (
    jd_collection,
    resume_collection,
)

logger = get_logger(__name__)


@dataclass
class IndexingResult:
    """Result of a document indexing operation."""

    collection_name: str
    chunks_indexed: int
    document_type: str
    source_file: str
    success: bool
    error_message: str = ""


class DocumentIndexer:
    """
    Indexes documents into ChromaDB for RAG retrieval.

    Called once per document upload. Clears any existing chunks for
    the collection before storing new ones so re-uploads are clean.

    Usage:
        indexer = DocumentIndexer(
            embedding_pipeline=pipeline,
            vector_store=chroma_repo,
        )
        result = indexer.index_resume(resume, session_id="session-abc")
        result = indexer.index_jd(jd, session_id="session-abc")
    """

    def __init__(
        self,
        embedding_pipeline: EmbeddingPipeline,
        vector_store: BaseVectorStore,
    ) -> None:
        self._pipeline = embedding_pipeline
        self._vector_store = vector_store
        logger.debug("DocumentIndexer initialised")

    def index_resume(self, resume: Resume, session_id: str) -> IndexingResult:
        """
        Embed and store all chunks from a parsed resume.

        Clears the existing resume collection for this session before
        indexing so re-uploads don't accumulate stale chunks.

        Args:
            resume: Parsed Resume domain model.
            session_id: Scopes the ChromaDB collection.

        Returns:
            IndexingResult with chunk count and success status.
        """
        collection = resume_collection(session_id)
        return self._index(
            text=resume.raw_text,
            source_file=resume.file_name,
            document_type="resume",
            collection_name=collection,
            extra_metadata={
                "resume_id": resume.resume_id,
                "candidate_name": resume.contact.name or "unknown",
            },
        )

    def index_jd(self, jd: JobDescription, session_id: str) -> IndexingResult:
        """
        Embed and store all chunks from a parsed job description.

        Args:
            jd: Parsed JobDescription domain model.
            session_id: Scopes the ChromaDB collection.

        Returns:
            IndexingResult with chunk count and success status.
        """
        collection = jd_collection(session_id)
        return self._index(
            text=jd.raw_text,
            source_file=jd.file_name or "job_description",
            document_type="job_description",
            collection_name=collection,
            extra_metadata={
                "jd_id": jd.jd_id,
                "job_title": jd.job_title or "unknown",
            },
        )

    def index_document(
        self,
        document: ExtractedDocument,
        document_type: str,
        session_id: str,
    ) -> IndexingResult:
        """
        Index a raw ExtractedDocument directly.

        Used when the caller has an ExtractedDocument but hasn't run
        the full parser yet — e.g. for a quick RAG-only workflow.

        Args:
            document: ExtractedDocument from DocumentProcessingService.
            document_type: "resume" or "job_description".
            session_id: Scopes the ChromaDB collection.

        Returns:
            IndexingResult.
        """
        if document_type == "resume":
            collection = resume_collection(session_id)
        else:
            collection = jd_collection(session_id)

        return self._index(
            text=document.raw_text,
            source_file=document.file_name,
            document_type=document_type,
            collection_name=collection,
        )

    # ------------------------------------------------------------------ #
    #  Internal                                                           #
    # ------------------------------------------------------------------ #

    def _index(
        self,
        text: str,
        source_file: str,
        document_type: str,
        collection_name: str,
        extra_metadata: dict | None = None,
    ) -> IndexingResult:
        """
        Core indexing implementation shared by all public methods.

        Steps:
        1. Delete existing collection (idempotent re-index)
        2. Run EmbeddingPipeline → list[DocumentChunk]
        3. Store in ChromaDB via vector_store.add_documents()

        Args:
            text: Full cleaned document text.
            source_file: Filename for metadata.
            document_type: "resume" or "job_description".
            collection_name: Target ChromaDB collection.
            extra_metadata: Additional metadata to attach to all chunks.

        Returns:
            IndexingResult.
        """
        logger.info(
            "Indexing document",
            extra={
                "collection": collection_name,
                "source": source_file,
                "type": document_type,
            },
        )

        try:
            # Clear stale chunks before re-indexing
            self._vector_store.delete_collection(collection_name)

            # Generate chunks + embeddings
            embedding_result = self._pipeline.embed_document(
                text=text,
                source_file=source_file,
                document_type=document_type,
                extra_metadata=extra_metadata,
            )

            if embedding_result.is_empty:
                logger.warning(
                    "No chunks produced — document may be empty",
                    extra={"source": source_file},
                )
                return IndexingResult(
                    collection_name=collection_name,
                    chunks_indexed=0,
                    document_type=document_type,
                    source_file=source_file,
                    success=False,
                    error_message="No chunks produced from document text.",
                )

            # Store in vector database
            self._vector_store.add_documents(
                collection_name, embedding_result.chunks
            )

            logger.info(
                "Document indexed successfully",
                extra={
                    "collection": collection_name,
                    "chunks": embedding_result.total_chunks,
                },
            )

            return IndexingResult(
                collection_name=collection_name,
                chunks_indexed=embedding_result.total_chunks,
                document_type=document_type,
                source_file=source_file,
                success=True,
            )

        except Exception as e:
            logger.error(
                "Document indexing failed",
                extra={"collection": collection_name, "error": str(e)},
            )
            return IndexingResult(
                collection_name=collection_name,
                chunks_indexed=0,
                document_type=document_type,
                source_file=source_file,
                success=False,
                error_message=str(e),
            )
