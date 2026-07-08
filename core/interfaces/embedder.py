"""
Embedder Interface.

Abstract contract for all embedding implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """
    Abstract base class for embedding models.

    Swap sentence-transformers for OpenAI or Cohere embeddings
    by implementing this interface.
    """

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """
        Embed a single string into a vector.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple strings in one batch.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output vector dimension."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Embedding model identifier."""
        ...
