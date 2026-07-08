"""
Vector Store Interface.

Abstract contract for all vector database implementations.
Services use BaseVectorStore — never ChromaDB directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocumentChunk:
    """A single document chunk ready for embedding and storage."""

    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None


@dataclass
class SearchResult:
    """A retrieved document chunk with its similarity score."""

    chunk_id: str
    content: str
    metadata: dict
    score: float  # Cosine similarity — higher = more relevant


class BaseVectorStore(ABC):
    """
    Abstract base class for vector store implementations.

    Defines the contract for document storage and retrieval.
    Swap ChromaDB for Pinecone, Weaviate, or FAISS by implementing
    this interface — zero changes to RAG or other services.
    """

    @abstractmethod
    def add_documents(
        self,
        collection_name: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """
        Store document chunks with their embeddings.

        Args:
            collection_name: Target collection/namespace.
            chunks: List of chunks with pre-computed embeddings.

        Raises:
            VectorStoreError: On storage failure.
        """
        ...

    @abstractmethod
    def similarity_search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Retrieve top-k most similar chunks to a query embedding.

        Args:
            collection_name: Collection to search.
            query_embedding: Query vector.
            top_k: Maximum results to return.
            score_threshold: Minimum similarity score.
            metadata_filter: Optional metadata constraints.

        Returns:
            List of SearchResult ordered by score descending.
        """
        ...

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """Delete all documents in a collection."""
        ...

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists and has documents."""
        ...

    @abstractmethod
    def get_document_count(self, collection_name: str) -> int:
        """Return number of chunks stored in a collection."""
        ...


class VectorStoreError(Exception):
    """Raised when a vector store operation fails."""
    pass
