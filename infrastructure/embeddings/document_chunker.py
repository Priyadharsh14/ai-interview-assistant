"""
Document Chunker.

Splits document text into overlapping chunks suitable for embedding
and vector store storage.

Chunking strategy:
- Split on paragraph boundaries first (natural semantic units)
- If a paragraph exceeds max_chars, split on sentence boundaries
- Overlap between chunks preserves context across boundaries
- Each chunk carries metadata for source tracking in RAG

Why overlap matters:
    A fact that spans a chunk boundary (e.g. a skill mentioned at the
    end of one chunk and its context in the next) would be lost without
    overlap. Overlapping ensures retrieval can find relevant context even
    when the key information sits near a chunk edge.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TextChunk:
    """
    A single chunk of document text ready for embedding.

    Carries metadata that flows through to ChromaDB and back to the
    RAG pipeline for source attribution.
    """

    chunk_id: str
    content: str
    chunk_index: int
    total_chunks: int       # Set after all chunks are created
    source_file: str
    document_type: str      # "resume" or "job_description"
    word_count: int = 0
    char_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.word_count:
            self.word_count = len(self.content.split())
        if not self.char_count:
            self.char_count = len(self.content)

    def to_metadata_dict(self) -> dict:
        """
        Flatten chunk metadata for ChromaDB storage.

        ChromaDB metadata must be a flat dict of str/int/float/bool values.
        """
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "source_file": self.source_file,
            "document_type": self.document_type,
            "word_count": self.word_count,
            "char_count": self.char_count,
            **{k: v for k, v in self.metadata.items()
               if isinstance(v, (str, int, float, bool))},
        }


class DocumentChunker:
    """
    Splits document text into overlapping chunks for embedding.

    Uses a two-level strategy:
    1. Split on paragraph boundaries (double newlines)
    2. If any paragraph is too long, split further on sentence boundaries
    3. Apply character-level overlap between consecutive chunks

    Configuration is read from settings but can be overridden in tests.
    """

    # Sentence boundary pattern — ends with . ! ? followed by whitespace
    _SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+')

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        """
        Args:
            chunk_size: Target maximum characters per chunk.
                        (Not words — chars are more predictable for embedders.)
            chunk_overlap: Characters of overlap between consecutive chunks.
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @classmethod
    def from_settings(cls) -> "DocumentChunker":
        """Construct using values from application settings."""
        from config.settings import get_settings
        s = get_settings().chunking
        # Convert token-based settings to approximate char counts (1 token ≈ 4 chars)
        return cls(
            chunk_size=s.chunk_size * 4,
            chunk_overlap=s.chunk_overlap * 4,
        )

    def chunk_document(
        self,
        text: str,
        source_file: str,
        document_type: str,
        extra_metadata: Optional[dict] = None,
    ) -> list[TextChunk]:
        """
        Split document text into overlapping chunks.

        Args:
            text: Full cleaned document text.
            source_file: Original filename for metadata/source tracking.
            document_type: "resume" or "job_description".
            extra_metadata: Additional key-value pairs to attach to every chunk.

        Returns:
            List of TextChunk objects, each with content and metadata.
            Returns a single chunk if text is short enough to fit in one.
        """
        if not text or not text.strip():
            return []

        raw_chunks = self._split_into_chunks(text)

        chunks = []
        for i, content in enumerate(raw_chunks):
            if not content.strip():
                continue

            chunk = TextChunk(
                chunk_id=str(uuid.uuid4()),
                content=content.strip(),
                chunk_index=i,
                total_chunks=0,          # Filled in below
                source_file=source_file,
                document_type=document_type,
                metadata=extra_metadata or {},
            )
            chunks.append(chunk)

        # Back-fill total_chunks now that we know the count
        total = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total

        return chunks

    # ------------------------------------------------------------------ #
    #  Internal splitting logic                                           #
    # ------------------------------------------------------------------ #

    def _split_into_chunks(self, text: str) -> list[str]:
        """
        Core splitting algorithm.

        Steps:
        1. Split text into paragraphs on double-newlines
        2. Merge short paragraphs with the previous chunk to avoid
           tiny chunks that carry little semantic meaning
        3. Split long paragraphs at sentence boundaries
        4. Apply sliding window overlap between consecutive chunks

        Returns:
            List of chunk strings before metadata attachment.
        """
        paragraphs = self._split_paragraphs(text)
        segments = self._merge_short_paragraphs(paragraphs)
        segments = self._split_long_segments(segments)
        return self._apply_overlap(segments)

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split on blank lines, filtering empty results."""
        parts = re.split(r'\n{2,}', text)
        return [p.strip() for p in parts if p.strip()]

    def _merge_short_paragraphs(self, paragraphs: list[str]) -> list[str]:
        """
        Merge consecutive short paragraphs until the chunk_size is reached.

        A paragraph shorter than 20% of chunk_size by itself carries
        too little context to be a useful retrieval unit.
        """
        min_size = self.chunk_size // 5
        merged: list[str] = []
        buffer = ""

        for para in paragraphs:
            if not buffer:
                buffer = para
            elif len(buffer) + len(para) + 2 <= self.chunk_size:
                buffer = buffer + "\n\n" + para
            elif len(buffer) < min_size:
                # Buffer too short — keep merging even over chunk_size
                buffer = buffer + "\n\n" + para
            else:
                merged.append(buffer)
                buffer = para

        if buffer:
            merged.append(buffer)

        return merged

    def _split_long_segments(self, segments: list[str]) -> list[str]:
        """
        Split segments that exceed chunk_size at sentence boundaries.

        Falls back to hard character splits if no sentence boundary
        is found within a reasonable range.
        """
        result = []
        for seg in segments:
            if len(seg) <= self.chunk_size:
                result.append(seg)
            else:
                result.extend(self._split_at_sentences(seg))
        return result

    def _split_at_sentences(self, text: str) -> list[str]:
        """Split a long segment into sentence-boundary-respecting chunks."""
        sentences = self._SENTENCE_BOUNDARY.split(text)
        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            candidate = (current + " " + sentence).strip() if current else sentence
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # If a single sentence is over chunk_size, hard-split it
                if len(sentence) > self.chunk_size:
                    chunks.extend(self._hard_split(sentence))
                    current = ""
                else:
                    current = sentence

        if current:
            chunks.append(current)

        return chunks

    def _hard_split(self, text: str) -> list[str]:
        """
        Last-resort character-level split for extremely long single sentences.

        Splits at word boundaries within chunk_size.
        """
        chunks = []
        while len(text) > self.chunk_size:
            # Find the last space within chunk_size
            split_at = text.rfind(" ", 0, self.chunk_size)
            if split_at == -1:
                split_at = self.chunk_size
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        if text:
            chunks.append(text)
        return chunks

    def _apply_overlap(self, segments: list[str]) -> list[str]:
        """
        Add overlap between consecutive chunks.

        Takes the last `chunk_overlap` characters from each chunk
        and prepends them to the next chunk.
        """
        if len(segments) <= 1 or self.chunk_overlap == 0:
            return segments

        overlapped: list[str] = [segments[0]]
        for i in range(1, len(segments)):
            prev = segments[i - 1]
            overlap_text = prev[-self.chunk_overlap:].strip()
            current = segments[i]

            # Only prepend overlap if it adds meaningful context
            if overlap_text and not current.startswith(overlap_text):
                overlapped.append(overlap_text + " " + current)
            else:
                overlapped.append(current)

        return overlapped
