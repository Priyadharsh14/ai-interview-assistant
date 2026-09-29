"""
RAG (Retrieval-Augmented Generation) Service.

Implements the complete RAG pipeline for document-grounded Q&A.

Full pipeline per query:
    User question
    → embed_query()           — convert to vector
    → similarity_search()     — retrieve top-k relevant chunks
    → build_context()         — format chunks into a coherent context block
    → build_prompt()          — inject context + question into LLM prompt
    → llm.generate()          — produce a grounded response
    → RAGResponse             — answer + sources + metadata

Two retrieval modes:
    "resume"          — searches the resume collection only
    "jd"              — searches the JD collection only
    "both"            — searches both and merges results by score

Design decisions:
    - Context window budget: cap total context at MAX_CONTEXT_CHARS to
      avoid overflowing the model's context window
    - Source attribution: every response carries chunk IDs and source
      file names so the UI can show "based on your resume, page 1"
    - Fallback: if retrieval returns nothing, the LLM still responds
      but the answer is flagged as non-grounded
    - Conversation history: accepts optional prior turns so the LLM
      has multi-turn context (full history managed by ConversationMemory
      in Phase 15)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from config.logging_config import get_logger
from config.settings import get_settings
from core.domain.interview import ChatMessage
from core.interfaces.embedder import BaseEmbedder
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage
from core.interfaces.vector_store import BaseVectorStore, SearchResult
from infrastructure.llm.prompt_templates import rag_assistant_system, rag_user_prompt
from infrastructure.vector_store.collection_names import (
    jd_collection,
    resume_collection,
)

logger = get_logger(__name__)

RetrievalMode = Literal["resume", "jd", "both"]

# Maximum characters of retrieved context to inject into the prompt.
# Prevents overflowing the model's 32k context window.
MAX_CONTEXT_CHARS = 6_000


@dataclass
class RAGResponse:
    """
    Complete response from the RAG pipeline.

    Carries the answer, the source chunks that grounded it,
    and metadata about the retrieval quality.
    """

    answer: str
    sources: list[SearchResult]
    is_grounded: bool          # False when no relevant chunks were found
    retrieval_mode: RetrievalMode
    chunks_retrieved: int
    query: str

    @property
    def source_files(self) -> list[str]:
        """Unique source file names cited in this response."""
        seen: set[str] = set()
        files = []
        for s in self.sources:
            name = s.metadata.get("source_file", "unknown")
            if name not in seen:
                seen.add(name)
                files.append(name)
        return files

    @property
    def avg_relevance_score(self) -> float:
        """Mean similarity score of retrieved chunks."""
        if not self.sources:
            return 0.0
        return round(sum(s.score for s in self.sources) / len(self.sources), 3)


class RAGService:
    """
    Document-grounded question answering using RAG.

    Accepts a session_id that scopes ChromaDB collection lookups —
    each user/session has their own isolated resume and JD collections.

    Usage:
        service = RAGService(
            llm=groq_provider,
            embedder=sentence_transformer_embedder,
            vector_store=chroma_repository,
            session_id="user-session-abc123",
        )
        response = service.query(
            question="What Python frameworks does the candidate know?",
            mode="resume",
        )
        print(response.answer)
        print(response.source_files)
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        session_id: str,
    ) -> None:
        """
        Args:
            llm: Any BaseLLMProvider (Groq in production, mock in tests).
            embedder: Any BaseEmbedder (SentenceTransformer in production).
            vector_store: Any BaseVectorStore (ChromaRepository in production).
            session_id: Scopes collection lookups to this user/session.
        """
        self._llm = llm
        self._embedder = embedder
        self._vector_store = vector_store
        self._session_id = session_id

        settings = get_settings()
        self._top_k = settings.vector_store.retrieval_top_k
        self._score_threshold = settings.vector_store.retrieval_score_threshold

        logger.debug(
            "RAGService initialised",
            extra={"session_id": session_id, "top_k": self._top_k},
        )

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def query(
        self,
        question: str,
        mode: RetrievalMode = "both",
        conversation_history: list[ChatMessage] | None = None,
        top_k: int | None = None,
    ) -> RAGResponse:
        """
        Answer a question grounded in the user's uploaded documents.

        Args:
            question: User's question in natural language.
            mode: Which document(s) to retrieve from.
                  "resume" | "jd" | "both"
            conversation_history: Prior chat turns for multi-turn context.
                                  Provided by ConversationMemory in Phase 15.
            top_k: Override the configured retrieval count for this call.

        Returns:
            RAGResponse with answer, sources, and retrieval metadata.

        Raises:
            ValueError: If the question is empty.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        effective_k = top_k or self._top_k

        logger.info(
            "RAG query",
            extra={
                "session": self._session_id,
                "mode": mode,
                "question_preview": question[:80],
            },
        )

        # Step 1: Embed the question
        query_vector = self._embedder.embed_text(question)

        # Step 2: Retrieve relevant chunks
        retrieved = self._retrieve(query_vector, mode, effective_k)

        # Step 3: Build LLM prompt with context
        messages = self._build_messages(
            question=question,
            retrieved=retrieved,
            mode=mode,
            history=conversation_history or [],
        )

        # Step 4: Generate answer
        response = self._llm.generate(
            messages=messages,
            temperature=0.3,   # Slightly creative but grounded
            max_tokens=1024,
        )

        is_grounded = len(retrieved) > 0

        logger.info(
            "RAG query complete",
            extra={
                "chunks_retrieved": len(retrieved),
                "is_grounded": is_grounded,
                "answer_length": len(response.content),
            },
        )

        return RAGResponse(
            answer=response.content,
            sources=retrieved,
            is_grounded=is_grounded,
            retrieval_mode=mode,
            chunks_retrieved=len(retrieved),
            query=question,
        )

    async def stream_query(
        self,
        question: str,
        mode: RetrievalMode = "both",
        conversation_history: list[ChatMessage] | None = None,
    ):
        """
        Streaming version of query() for real-time UI updates.

        Yields token chunks as they arrive from the LLM.
        The caller is responsible for assembling the full response.

        Args:
            question: User question.
            mode: Retrieval mode.
            conversation_history: Prior chat turns.

        Yields:
            str token chunks.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        query_vector = self._embedder.embed_text(question)
        retrieved = self._retrieve(query_vector, mode, self._top_k)

        messages = self._build_messages(
            question=question,
            retrieved=retrieved,
            mode=mode,
            history=conversation_history or [],
        )

        async for token in self._llm.stream(messages=messages, temperature=0.3):
            yield token

    def is_document_indexed(self, mode: RetrievalMode = "both") -> bool:
        """
        Check whether the session's documents are indexed in ChromaDB.

        Used by the UI to guard the chat interface — if documents aren't
        indexed yet, the RAG service has nothing to retrieve from.

        Args:
            mode: Which collection(s) to check.

        Returns:
            True if all requested collections exist and are non-empty.
        """
        resume_col = resume_collection(self._session_id)
        jd_col = jd_collection(self._session_id)

        if mode == "resume":
            return self._vector_store.collection_exists(resume_col)
        if mode == "jd":
            return self._vector_store.collection_exists(jd_col)
        # "both" — require at least one to be indexed
        return (
            self._vector_store.collection_exists(resume_col)
            or self._vector_store.collection_exists(jd_col)
        )

    # ------------------------------------------------------------------ #
    #  Retrieval                                                          #
    # ------------------------------------------------------------------ #

    def _retrieve(
        self,
        query_vector: list[float],
        mode: RetrievalMode,
        top_k: int,
    ) -> list[SearchResult]:
        """
        Retrieve relevant chunks from the appropriate collection(s).

        For "both" mode: retrieves from each collection independently,
        then merges and re-sorts by score, keeping only the top_k best.

        Args:
            query_vector: Embedded query vector.
            mode: Which collection(s) to search.
            top_k: Maximum total results to return.

        Returns:
            SearchResult list sorted by score descending.
        """
        resume_col = resume_collection(self._session_id)
        jd_col = jd_collection(self._session_id)

        if mode == "resume":
            return self._vector_store.similarity_search(
                resume_col, query_vector, top_k, self._score_threshold
            )

        if mode == "jd":
            return self._vector_store.similarity_search(
                jd_col, query_vector, top_k, self._score_threshold
            )

        # "both": merge results from both collections
        resume_results = self._vector_store.similarity_search(
            resume_col, query_vector, top_k, self._score_threshold
        )
        jd_results = self._vector_store.similarity_search(
            jd_col, query_vector, top_k, self._score_threshold
        )

        merged = resume_results + jd_results
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:top_k]

    # ------------------------------------------------------------------ #
    #  Prompt construction                                                #
    # ------------------------------------------------------------------ #

    def _build_messages(
        self,
        question: str,
        retrieved: list[SearchResult],
        mode: RetrievalMode,
        history: list[ChatMessage],
    ) -> list[LLMMessage]:
        """
        Build the full message list for the LLM call.

        Structure:
            [system]       — persona + grounding instructions
            [assistant]*   — prior conversation turns (alternating)
            [user]*        — prior conversation turns
            [user]         — current question with injected context

        Args:
            question: Current user question.
            retrieved: Retrieved document chunks.
            mode: Used to customise the system prompt.
            history: Prior ChatMessage turns.

        Returns:
            List of LLMMessage ready to send to the provider.
        """
        doc_type_label = {
            "resume": "resume",
            "jd": "job description",
            "both": "resume and job description",
        }[mode]

        messages: list[LLMMessage] = [
            LLMMessage(
                role="system",
                content=rag_assistant_system(doc_type_label),
            )
        ]

        # Inject conversation history (last N turns to manage context budget)
        for turn in history[-6:]:   # Max 6 prior turns = 3 back-and-forth exchanges
            messages.append(LLMMessage(role=turn.role, content=turn.content))

        # Build context block from retrieved chunks
        context = self._build_context(retrieved)

        # Final user message with context injection
        messages.append(
            LLMMessage(
                role="user",
                content=rag_user_prompt(question, context),
            )
        )

        return messages

    def _build_context(self, results: list[SearchResult]) -> str:
        """
        Format retrieved chunks into a numbered context block.

        Each chunk is prefixed with its source file and relevance score
        so the LLM can attribute information and the user can see where
        each fact came from.

        Respects MAX_CONTEXT_CHARS to avoid context window overflow.

        Args:
            results: Retrieved SearchResult list.

        Returns:
            Formatted context string, or a "no context" fallback.
        """
        if not results:
            return (
                "No relevant document content was found for this query. "
                "Answer based on general knowledge and note this limitation."
            )

        context_parts: list[str] = []
        total_chars = 0

        for i, result in enumerate(results, 1):
            source = result.metadata.get("source_file", "document")
            score = result.score
            snippet = f"[Source {i}: {source} | relevance: {score:.2f}]\n{result.content}"

            if total_chars + len(snippet) > MAX_CONTEXT_CHARS:
                # Include a truncated version if we have budget for at least half
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining > len(snippet) // 2:
                    context_parts.append(snippet[:remaining] + "...")
                break

            context_parts.append(snippet)
            total_chars += len(snippet)

        return "\n\n---\n\n".join(context_parts)
