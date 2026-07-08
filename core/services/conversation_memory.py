"""
Conversation Memory Service.

Manages multi-turn chat history for the RAG assistant.

Responsibilities:
    1. Store and retrieve conversation turns per session
    2. Enforce a sliding-window token budget so history never
       overflows the LLM's context window
    3. Summarise old turns when the window fills up so context
       is preserved even after many exchanges
    4. Provide session isolation — resume chat, JD chat, and
       mock interview each maintain independent histories
    5. Export history in the LLMMessage format the RAGService expects

Memory architecture:
    Each session has one ConversationHistory (the full record).
    When history exceeds MAX_TURNS the service compresses the
    oldest turns into a single summary message, then continues.
    This is the "sliding window with summarisation" strategy —
    cheaper than storing embeddings for every message, more
    coherent than a fixed truncation window.

Session isolation:
    session_key = f"{session_id}:{context_type}"
    context_type ∈ {"resume_chat", "jd_chat", "general"}
    Each key has a completely independent ConversationHistory.
"""

from __future__ import annotations

from typing import Literal, Optional

from config.logging_config import get_logger
from core.domain.interview import ChatMessage, ConversationHistory
from core.interfaces.llm_provider import BaseLLMProvider, LLMMessage

logger = get_logger(__name__)

ContextType = Literal["resume_chat", "jd_chat", "general"]

# Maximum turns (user+assistant pairs) before summarisation triggers
MAX_TURNS = 10          # 10 pairs = 20 messages
# Minimum turns to keep verbatim after summarisation
KEEP_RECENT_TURNS = 4  # Last 4 pairs always kept in full

_SUMMARISE_SYSTEM = """You are a conversation summariser.
Compress the following conversation into 3–5 concise bullet points,
preserving all key facts, decisions, and context the user mentioned.
Write only the bullet points — no preamble or explanation."""


class ConversationMemoryService:
    """
    In-process conversation memory with sliding-window management.

    Stores histories in a dict keyed by session+context type.
    State is per-process — in Streamlit this means it is owned by
    Streamlit's session_state, not by this service directly.

    Usage:
        memory = ConversationMemoryService(llm=groq_provider)

        # Add a turn
        memory.add_turn(session_id, "resume_chat",
                        user_message="What Python skills do I have?",
                        assistant_message="You have Python, LangChain...",
                        sources=["chunk-id-1"])

        # Retrieve for RAG prompt injection
        history = memory.get_recent_history(session_id, "resume_chat")
        response = rag_service.query(question, conversation_history=history)

        # Clear when user starts fresh
        memory.clear_session(session_id, "resume_chat")
    """

    def __init__(self, llm: Optional[BaseLLMProvider] = None) -> None:
        """
        Args:
            llm: Optional LLM for history summarisation.
                 When None, summarisation falls back to hard truncation.
        """
        self._llm = llm
        self._store: dict[str, ConversationHistory] = {}
        logger.debug("ConversationMemoryService initialised")

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    def add_turn(
        self,
        session_id: str,
        context_type: ContextType,
        user_message: str,
        assistant_message: str,
        sources: Optional[list[str]] = None,
    ) -> None:
        """
        Record one complete exchange (user message + assistant response).

        Automatically triggers summarisation if history exceeds MAX_TURNS.

        Args:
            session_id: Unique identifier for this user/Streamlit session.
            context_type: "resume_chat" | "jd_chat" | "general"
            user_message: What the user asked.
            assistant_message: What the assistant responded.
            sources: Optional list of chunk IDs cited in the response.
        """
        key = self._key(session_id, context_type)
        history = self._get_or_create(key)

        history.add_message("user", user_message)
        history.add_message("assistant", assistant_message, sources=sources)

        # Trigger summarisation if over budget
        if self._turn_count(history) > MAX_TURNS:
            self._compress(key, history)

        logger.debug(
            "Turn recorded",
            extra={
                "key": key,
                "turns": self._turn_count(history),
            },
        )

    def get_recent_history(
        self,
        session_id: str,
        context_type: ContextType,
        max_turns: Optional[int] = None,
    ) -> list[ChatMessage]:
        """
        Return recent messages for injection into the RAG prompt.

        Args:
            session_id: Session identifier.
            context_type: Context namespace.
            max_turns: Override the default window size.
                       Returns last max_turns*2 messages.

        Returns:
            List of ChatMessage in chronological order.
            Empty list if no history exists for this key.
        """
        key = self._key(session_id, context_type)
        history = self._store.get(key)
        if not history:
            return []

        limit = (max_turns or KEEP_RECENT_TURNS) * 2
        return history.messages[-limit:]

    def get_full_history(
        self,
        session_id: str,
        context_type: ContextType,
    ) -> ConversationHistory:
        """
        Return the full ConversationHistory for a session+context.

        Creates an empty history if none exists.

        Args:
            session_id: Session identifier.
            context_type: Context namespace.

        Returns:
            ConversationHistory (may be empty).
        """
        key = self._key(session_id, context_type)
        return self._get_or_create(key)

    def get_llm_messages(
        self,
        session_id: str,
        context_type: ContextType,
        max_turns: Optional[int] = None,
    ) -> list[LLMMessage]:
        """
        Return recent history formatted as LLMMessage objects.

        This is the format that BaseLLMProvider.generate() expects,
        so RAGService can inject history directly without conversion.

        Args:
            session_id: Session identifier.
            context_type: Context namespace.
            max_turns: Optional window override.

        Returns:
            List of LLMMessage ready for the LLM provider.
        """
        chat_messages = self.get_recent_history(session_id, context_type, max_turns)
        return [
            LLMMessage(role=msg.role, content=msg.content)
            for msg in chat_messages
        ]

    def clear_session(
        self,
        session_id: str,
        context_type: ContextType,
    ) -> None:
        """
        Delete all history for a session+context.

        Called when the user uploads a new document or starts a fresh chat.

        Args:
            session_id: Session identifier.
            context_type: Context namespace to clear.
        """
        key = self._key(session_id, context_type)
        if key in self._store:
            del self._store[key]
            logger.info("Session history cleared", extra={"key": key})

    def clear_all(self, session_id: str) -> None:
        """
        Delete all history for a session across all context types.

        Called on full session reset.

        Args:
            session_id: Session identifier.
        """
        keys_to_delete = [k for k in self._store if k.startswith(f"{session_id}:")]
        for key in keys_to_delete:
            del self._store[key]
        if keys_to_delete:
            logger.info(
                "All session history cleared",
                extra={"session_id": session_id, "contexts_cleared": len(keys_to_delete)},
            )

    def message_count(
        self,
        session_id: str,
        context_type: ContextType,
    ) -> int:
        """
        Return the total number of messages stored for a session+context.

        Args:
            session_id: Session identifier.
            context_type: Context namespace.

        Returns:
            Message count (0 if no history exists).
        """
        key = self._key(session_id, context_type)
        history = self._store.get(key)
        return len(history.messages) if history else 0

    def has_history(
        self,
        session_id: str,
        context_type: ContextType,
    ) -> bool:
        """
        Return True if any messages exist for this session+context.

        Args:
            session_id: Session identifier.
            context_type: Context namespace.
        """
        return self.message_count(session_id, context_type) > 0

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _compress(
        self,
        key: str,
        history: ConversationHistory,
    ) -> None:
        """
        Compress old turns to keep history within budget.

        Strategy:
        1. Take all messages except the last KEEP_RECENT_TURNS*2
        2. Summarise them into a single assistant message via LLM
           (or via simple concatenation if LLM is unavailable)
        3. Replace compressed messages with the summary
        4. Append the recent messages back

        Args:
            key: Store key for logging.
            history: ConversationHistory to compress in place.
        """
        all_messages = history.messages
        keep_count = KEEP_RECENT_TURNS * 2
        old_messages = all_messages[:-keep_count] if len(all_messages) > keep_count else []
        recent_messages = all_messages[-keep_count:]

        if not old_messages:
            return

        logger.info(
            "Compressing conversation history",
            extra={"key": key, "compressing": len(old_messages)},
        )

        summary = self._summarise(old_messages)

        # Rebuild history: summary first, then recent verbatim
        history.messages = [
            ChatMessage(
                role="assistant",
                content=f"[Conversation summary]\n{summary}",
            )
        ] + list(recent_messages)

        logger.info(
            "History compressed",
            extra={"key": key, "new_length": len(history.messages)},
        )

    def _summarise(self, messages: list[ChatMessage]) -> str:
        """
        Summarise a list of messages into a compact bullet-point summary.

        Falls back to a simple concatenation if the LLM is unavailable.

        Args:
            messages: Messages to summarise.

        Returns:
            Summary string.
        """
        if not self._llm:
            return self._truncation_fallback(messages)

        conversation_text = "\n".join(
            f"{msg.role.upper()}: {msg.content[:300]}"
            for msg in messages
        )

        try:
            response = self._llm.generate(
                messages=[
                    LLMMessage(role="system", content=_SUMMARISE_SYSTEM),
                    LLMMessage(
                        role="user",
                        content=f"Summarise this conversation:\n\n{conversation_text}",
                    ),
                ],
                temperature=0.1,
                max_tokens=512,
            )
            return response.content.strip()
        except Exception as e:
            logger.warning(
                "LLM summarisation failed — using truncation fallback",
                extra={"error": str(e)},
            )
            return self._truncation_fallback(messages)

    @staticmethod
    def _truncation_fallback(messages: list[ChatMessage]) -> str:
        """
        Simple fallback: concatenate message excerpts as bullet points.

        Args:
            messages: Messages to compress.

        Returns:
            Bullet-point summary string.
        """
        lines: list[str] = []
        for msg in messages:
            excerpt = msg.content[:150].replace("\n", " ")
            lines.append(f"- [{msg.role}] {excerpt}...")
        return "\n".join(lines)

    @staticmethod
    def _key(session_id: str, context_type: ContextType) -> str:
        """Build the internal store key."""
        return f"{session_id}:{context_type}"

    def _get_or_create(self, key: str) -> ConversationHistory:
        """Return existing history or create a fresh one."""
        if key not in self._store:
            session_id = key.split(":")[0]
            self._store[key] = ConversationHistory(session_id=session_id)
        return self._store[key]

    @staticmethod
    def _turn_count(history: ConversationHistory) -> int:
        """Return number of complete user+assistant pairs."""
        return len(history.messages) // 2
