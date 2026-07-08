"""
Embedding Pipeline Service.

Orchestrates the full document → chunks → embeddings workflow.
This is the bridge between document processing and vector storage.

Pipeline:
    Document text
    → DocumentChunker  (split into overlapping chunks)
    → BaseEmbedder     (generate vectors for each chunk)
    → list[DocumentChunk] (with embeddings attached, ready for ChromaDB)

Separation of concerns:
- This service knows about chunking strategy and embedding coordination
- It does NOT know about ChromaDB — storage is handled by the vector store
- It does NOT know about Groq — embeddings are local sentence-transformers
"""

from __future__ import annotations

from dataclasses import dataclass

from config.logging_config import get_logger
from core.interfaces.embedder import BaseEmbedder
from core.interfaces.vector_store import DocumentChunk
from infrastructure.embeddings.document_chunker import DocumentChunker, TextChunk

logger = get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding a full document."""

    source_file: str
    document_type: str
    chunks: list[DocumentChunk]
    total_chunks: int
    embedding_dimension: int
    model_name: str

    @property
    def is_empty(self) -> bool:
        return self.total_chunks == 0


class EmbeddingPipeline:
    """
    Coordinates chunking and embedding for document indexing.

    Receives dependencies via constructor injection — fully testable
    with mock embedders and custom chunkers.

    Usage:
        pipeline = EmbeddingPipeline(embedder=embedder, chunker=chunker)
        result = pipeline.embed_document(
            text="Senior Python Engineer...",
            source_file="resume.pdf",
            document_type="resume",
        )
        # result.chunks is ready to pass to ChromaRepository.add_documents()
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        chunker: DocumentChunker | None = None,
    ) -> None:
        """
        Args:
            embedder: Any BaseEmbedder implementation.
            chunker: DocumentChunker instance. Defaults to settings-based config.
        """
        self._embedder = embedder
        self._chunker = chunker or DocumentChunker.from_settings()
        logger.debug(
            "EmbeddingPipeline initialised",
            extra={
                "embedder": embedder.model_name,
                "chunk_size": self._chunker.chunk_size,
                "chunk_overlap": self._chunker.chunk_overlap,
            },
        )

    def embed_document(
        self,
        text: str,
        source_file: str,
        document_type: str,
        extra_metadata: dict | None = None,
    ) -> EmbeddingResult:
        """
        Chunk a document and generate embeddings for all chunks.

        Uses batch embedding for efficiency — one model call for all
        chunks rather than one call per chunk.

        Args:
            text: Full cleaned document text.
            source_file: Filename for metadata/source tracking.
            document_type: "resume" or "job_description".
            extra_metadata: Extra key-value pairs attached to every chunk.

        Returns:
            EmbeddingResult containing ready-to-store DocumentChunks.
        """
        logger.info(
            "Starting embedding pipeline",
            extra={"source": source_file, "type": document_type},
        )

        # Step 1: Chunk the document
        text_chunks: list[TextChunk] = self._chunker.chunk_document(
            text=text,
            source_file=source_file,
            document_type=document_type,
            extra_metadata=extra_metadata,
        )

        if not text_chunks:
            logger.warning(
                "No chunks produced — document may be empty",
                extra={"source": source_file},
            )
            return EmbeddingResult(
                source_file=source_file,
                document_type=document_type,
                chunks=[],
                total_chunks=0,
                embedding_dimension=self._embedder.dimension,
                model_name=self._embedder.model_name,
            )

        # Step 2: Batch embed all chunk contents
        contents = [chunk.content for chunk in text_chunks]
        embeddings = self._embedder.embed_batch(contents)

        # Step 3: Attach embeddings to DocumentChunk objects (vector store format)
        document_chunks: list[DocumentChunk] = []
        for text_chunk, embedding in zip(text_chunks, embeddings):
            doc_chunk = DocumentChunk(
                chunk_id=text_chunk.chunk_id,
                content=text_chunk.content,
                metadata=text_chunk.to_metadata_dict(),
                embedding=embedding,
            )
            document_chunks.append(doc_chunk)

        logger.info(
            "Embedding pipeline complete",
            extra={
                "source": source_file,
                "chunks": len(document_chunks),
                "dimension": self._embedder.dimension,
            },
        )

        return EmbeddingResult(
            source_file=source_file,
            document_type=document_type,
            chunks=document_chunks,
            total_chunks=len(document_chunks),
            embedding_dimension=self._embedder.dimension,
            model_name=self._embedder.model_name,
        )

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query string for similarity search.

        Used by the RAG pipeline to convert a user question into a
        vector for ChromaDB retrieval.

        Args:
            query: User's question or search query.

        Returns:
            Embedding vector as list of floats.
        """
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty")

        return self._embedder.embed_text(query)
