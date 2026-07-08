"""
Sentence Transformer Embedder.

Concrete implementation of BaseEmbedder using sentence-transformers.
Runs fully locally — no API key or network call required after first
model download.

Design decisions:
- Model is loaded once at construction and reused (expensive to reload)
- Singleton pattern via module-level cache prevents duplicate loads
- Batch embedding is significantly faster than single-text loops
- Normalise embeddings to unit length for cosine similarity compatibility
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from config.logging_config import get_logger
from config.settings import get_settings
from core.interfaces.embedder import BaseEmbedder

logger = get_logger(__name__)

# Module-level lock prevents multiple threads loading the same model
_model_lock = threading.Lock()


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Local embedding model using sentence-transformers.

    Default model: all-MiniLM-L6-v2
    - Dimension: 384
    - Speed: ~14,000 sentences/sec on CPU
    - Quality: Strong for semantic similarity tasks

    The model is downloaded on first use (~90MB) and cached locally
    by the sentence-transformers library.

    Usage:
        embedder = SentenceTransformerEmbedder()
        vector = embedder.embed_text("Python developer with 3 years experience")
        # vector is a list of 384 floats
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        """
        Load the sentence-transformer model.

        Args:
            model_name: Override the configured model. Useful in tests
                        to load a tiny model like 'all-MiniLM-L6-v2'.
        """
        settings = get_settings()
        self._model_name = model_name or settings.embedding.embedding_model
        self._batch_size = settings.embedding.embedding_batch_size
        self._device = settings.embedding.embedding_device

        logger.info(
            "Loading sentence-transformer model",
            extra={"model": self._model_name, "device": self._device},
        )

        with _model_lock:
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
            )

        # Cache the dimension after loading
        self._dimension = self._model.get_sentence_embedding_dimension()

        logger.info(
            "Embedding model loaded",
            extra={"model": self._model_name, "dimension": self._dimension},
        )

    # ------------------------------------------------------------------ #
    #  BaseEmbedder interface                                             #
    # ------------------------------------------------------------------ #

    def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text string into a normalised vector.

        Args:
            text: Input text. Empty strings return a zero vector.

        Returns:
            List of floats with length == self.dimension.
        """
        if not text or not text.strip():
            logger.warning("embed_text called with empty string — returning zero vector")
            return [0.0] * self._dimension

        embedding = self._model.encode(
            text,
            normalize_embeddings=True,   # Unit-length for cosine similarity
            show_progress_bar=False,
        )
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts in batches for efficiency.

        Empty/whitespace strings in the input are replaced with a
        zero vector rather than raising an error.

        Args:
            texts: List of input strings.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # Track which indices are empty so we can fill with zero vectors
        empty_indices = {i for i, t in enumerate(texts) if not t or not t.strip()}
        non_empty = [t if t and t.strip() else "." for t in texts]

        embeddings = self._model.encode(
            non_empty,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        result = []
        for i, emb in enumerate(embeddings):
            if i in empty_indices:
                result.append([0.0] * self._dimension)
            else:
                result.append(emb.tolist())

        return result

    @property
    def dimension(self) -> int:
        """Output vector dimension (384 for all-MiniLM-L6-v2)."""
        return self._dimension

    @property
    def model_name(self) -> str:
        """Sentence-transformers model identifier."""
        return self._model_name

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """
        Compute cosine similarity between two embeddings.

        Since embeddings are unit-normalised, this is just the dot product.
        Returns a value in [-1, 1] where 1 = identical, 0 = unrelated.

        Args:
            vec_a: First embedding vector.
            vec_b: Second embedding vector.

        Returns:
            Cosine similarity score.
        """
        a = np.array(vec_a)
        b = np.array(vec_b)
        return float(np.dot(a, b))


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformerEmbedder:
    """
    Return the cached embedder singleton.

    Uses lru_cache so the model is loaded exactly once per process.
    Call get_embedder.cache_clear() in tests to force a reload.
    """
    return SentenceTransformerEmbedder()
