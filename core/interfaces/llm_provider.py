"""
LLM Provider Interface.

Defines the abstract contract that all LLM providers must implement.
Business logic depends ONLY on this interface — never on concrete providers.

This is the Dependency Inversion Principle in practice:
    High-level modules (services) depend on abstractions.
    Low-level modules (GroqProvider) implement those abstractions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class LLMResponse:
    """Structured response from an LLM provider."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = "stop"

    @property
    def total_cost_estimate(self) -> float:
        """Rough cost estimate — providers override with real pricing."""
        return 0.0


@dataclass
class LLMMessage:
    """A single message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    Any LLM (Groq, OpenAI, Gemini, Ollama) must implement this interface.
    Services receive a BaseLLMProvider instance via dependency injection
    and never import concrete provider classes directly.

    Example:
        class MyService:
            def __init__(self, llm: BaseLLMProvider) -> None:
                self._llm = llm

            def analyze(self, text: str) -> str:
                response = self._llm.generate(
                    messages=[LLMMessage(role="user", content=text)]
                )
                return response.content
    """

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from a list of messages.

        Args:
            messages: Conversation history including system, user, assistant turns.
            temperature: Override the default temperature for this call.
            max_tokens: Override the default max tokens for this call.

        Returns:
            LLMResponse with content and token usage.

        Raises:
            LLMProviderError: On API failure, timeout, or rate limit.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Stream response tokens as they are generated.

        Args:
            messages: Conversation history.
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Yields:
            String token chunks as they arrive.

        Raises:
            LLMProviderError: On API failure or timeout.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verify the provider is reachable and the API key is valid.

        Returns:
            True if healthy, False otherwise.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. 'Groq/Llama-3.3')."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier."""
        ...


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails."""

    def __init__(self, message: str, provider: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
