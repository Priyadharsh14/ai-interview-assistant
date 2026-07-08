"""
ChromaDB Vector Store Repository.

Concrete implementation of BaseVectorStore using ChromaDB with
persistent on-disk storage.

Design decisions:
- One ChromaDB client per application process (singleton via get_chroma_repository)
- Collections are created lazily on first use — no manual setup required
- Embeddings are stored as provided (pre-computed by EmbeddingPipeline)
- ChromaDB's native distance is L2; we convert to cosine similarity scores
- Metadata is stored as flat dicts (ChromaDB requirement)
- Batch upsert in chunks of UPSERT_BATCH_SIZE to avoid memory spikes
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.logging_config import get_logger
from config.settings import get_settings
from core.interfaces.vector_store import (
    BaseVectorStore,
    DocumentChunk,
    SearchResult,
    VectorStoreError,
)

logger = get_logger(__name__)

# Maximum documents per ChromaDB upsert call to avoid memory spikes
UPSERT_BATCH_SIZE = 100


class ChromaRepository(BaseVectorStore):
    """
    Persistent ChromaDB vector store.

    Stores document chunks with embeddings and supports
    similarity search with optional metadata filtering.

    Collections are created automatically on first use.
    The same collection name maps to the same persistent storage
    across application restarts.

    Usage:
        repo = ChromaRepository()
        repo.add_documents("resume_collection", chunks)
        results = repo.similarity_search("resume_collection", query_vec, top_k=5)
    """

    def __init__(self, persist_directory: Optional[str] = None) -> None:
        """
        Initialise the ChromaDB client with persistent storage.

        Args:
            persist_directory: Override the configured persist path.
                               Useful in tests to use a temp directory.
        """
        settings = get_settings()
        self._persist_dir = (
            persist_directory or settings.vector_store.chroma_persist_directory
        )

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        logger.info(
            "ChromaRepository initialised",
            extra={"persist_dir": self._persist_dir},
        )

    # ------------------------------------------------------------------ #
    #  BaseVectorStore interface                                          #
    # ------------------------------------------------------------------ #

    def add_documents(
        self,
        collection_name: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """
        Upsert document chunks with their embeddings into a collection.

        Uses upsert (not insert) so re-indexing a document replaces
        existing chunks rather than creating duplicates.

        Args:
            collection_name: Target ChromaDB collection.
            chunks: DocumentChunk list — each must have a non-None embedding.

        Raises:
            VectorStoreError: If chunks are missing embeddings or storage fails.
        """
        if not chunks:
            logger.warning("add_documents called with empty chunk list")
            return

        # Validate all chunks have embeddings before touching ChromaDB
        missing = [c.chunk_id for c in chunks if c.embedding is None]
        if missing:
            raise VectorStoreError(
                f"{len(missing)} chunk(s) are missing embeddings. "
                "Run EmbeddingPipeline before calling add_documents."
            )

        collection = self._get_or_create_collection(collection_name)

        try:
            # Batch upserts to avoid memory spikes on large documents
            for batch_start in range(0, len(chunks), UPSERT_BATCH_SIZE):
                batch = chunks[batch_start : batch_start + UPSERT_BATCH_SIZE]
                collection.upsert(
                    ids=[c.chunk_id for c in batch],
                    documents=[c.content for c in batch],
                    embeddings=[c.embedding for c in batch],
                    metadatas=[self._sanitize_metadata(c.metadata) for c in batch],
                )

            logger.info(
                "Documents stored in ChromaDB",
                extra={
                    "collection": collection_name,
                    "chunks_stored": len(chunks),
                },
            )

        except Exception as e:
            logger.error(
                "ChromaDB upsert failed",
                extra={"collection": collection_name, "error": str(e)},
            )
            raise VectorStoreError(f"Failed to store documents: {e}") from e

    def similarity_search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Retrieve top-k most similar chunks using cosine similarity.

        ChromaDB returns L2 distances; we convert to similarity scores
        in [0, 1] using: similarity = 1 - (distance / 2)
        (valid for unit-normalised embeddings where max L2 distance = 2)

        Args:
            collection_name: Collection to search in.
            query_embedding: Query vector from EmbeddingPipeline.embed_query().
            top_k: Maximum number of results.
            score_threshold: Minimum similarity score (0.0 = no filter).
            metadata_filter: ChromaDB where-clause dict for metadata filtering.

        Returns:
            SearchResult list ordered by score descending (most similar first).
            Returns empty list if the collection doesn't exist.
        """
        if not self.collection_exists(collection_name):
            logger.warning(
                "similarity_search on non-existent collection",
                extra={"collection": collection_name},
            )
            return []

        collection = self._get_or_create_collection(collection_name)
        doc_count = collection.count()

        if doc_count == 0:
            return []

        # Don't request more results than documents in the collection
        effective_k = min(top_k, doc_count)

        try:
            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": effective_k,
                "include": ["documents", "metadatas", "distances"],
            }
            if metadata_filter:
                query_kwargs["where"] = metadata_filter

            raw = collection.query(**query_kwargs)

        except Exception as e:
            logger.error(
                "ChromaDB query failed",
                extra={"collection": collection_name, "error": str(e)},
            )
            raise VectorStoreError(f"Similarity search failed: {e}") from e

        results = self._parse_query_results(raw, score_threshold)

        logger.debug(
            "Similarity search complete",
            extra={
                "collection": collection_name,
                "requested": top_k,
                "returned": len(results),
            },
        )

        return results

    def delete_collection(self, collection_name: str) -> None:
        """
        Permanently delete a collection and all its documents.

        Used when a user re-uploads a document — the old collection
        is cleared before the new one is indexed.

        Args:
            collection_name: Collection to delete.
        """
        try:
            self._client.delete_collection(collection_name)
            logger.info(
                "Collection deleted",
                extra={"collection": collection_name},
            )
        except Exception as e:
            # ChromaDB raises if the collection doesn't exist — treat as no-op
            logger.debug(
                "delete_collection — collection may not exist",
                extra={"collection": collection_name, "error": str(e)},
            )

    def collection_exists(self, collection_name: str) -> bool:
        """
        Return True if the collection exists and contains at least one document.

        Args:
            collection_name: Collection name to check.

        Returns:
            True if the collection exists and is non-empty.
        """
        try:
            collection = self._client.get_collection(collection_name)
            return collection.count() > 0
        except Exception:
            return False

    def get_document_count(self, collection_name: str) -> int:
        """
        Return the number of chunks stored in a collection.

        Args:
            collection_name: Collection name.

        Returns:
            Chunk count, or 0 if the collection doesn't exist.
        """
        try:
            collection = self._client.get_collection(collection_name)
            return collection.count()
        except Exception:
            return 0

    def reset_all(self) -> None:
        """
        Delete all collections. Used in integration tests only.

        Warning: This is destructive and irreversible.
        """
        self._client.reset()
        logger.warning("ChromaDB reset — all collections deleted")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _get_or_create_collection(self, name: str) -> chromadb.Collection:
        """
        Get an existing collection or create it if it doesn't exist.

        Uses cosine distance (most natural for normalised embeddings).
        ChromaDB's get_or_create_collection is idempotent.
        """
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _parse_query_results(
        raw: dict,
        score_threshold: float,
    ) -> list[SearchResult]:
        """
        Convert ChromaDB query output to SearchResult objects.

        ChromaDB returns nested lists (one per query):
            raw["ids"]       = [["id1", "id2", ...]]
            raw["documents"] = [["content1", "content2", ...]]
            raw["metadatas"] = [[{...}, {...}, ...]]
            raw["distances"] = [[0.12, 0.34, ...]]

        Cosine distance ∈ [0, 2] for unit vectors.
        Similarity = 1 - distance  (1.0 = identical, 0.0 = orthogonal)

        Args:
            raw: Raw ChromaDB query response dict.
            score_threshold: Filter out results below this similarity.

        Returns:
            Filtered, sorted SearchResult list.
        """
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results = []
        for chunk_id, content, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            # Convert cosine distance → similarity score
            similarity = max(0.0, 1.0 - distance)

            if similarity < score_threshold:
                continue

            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    content=content,
                    metadata=metadata or {},
                    score=round(similarity, 4),
                )
            )

        # Sort by score descending (most similar first)
        return sorted(results, key=lambda r: r.score, reverse=True)

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        """
        Ensure metadata dict only contains ChromaDB-compatible types.

        ChromaDB accepts: str, int, float, bool — nothing else.
        Lists, dicts, and None values are converted or removed.

        Args:
            metadata: Raw metadata dict from TextChunk.

        Returns:
            Cleaned flat metadata dict.
        """
        clean = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif value is None:
                clean[key] = ""
            else:
                # Convert non-scalar values to string representation
                clean[key] = str(value)
        return clean


@lru_cache(maxsize=1)
def get_chroma_repository() -> ChromaRepository:
    """
    Return the application-wide ChromaRepository singleton.

    Uses lru_cache so the ChromaDB client is initialised once per process.
    Call get_chroma_repository.cache_clear() in tests to reset.
    """
    return ChromaRepository()
