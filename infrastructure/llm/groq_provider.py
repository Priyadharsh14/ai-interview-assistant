"""
Groq LLM Provider.

Concrete implementation of BaseLLMProvider using the Groq API
with GPT-OSS 120B as the active model.

Features:
- Automatic retry with exponential backoff (tenacity)
- Token usage tracking on every call
- Streaming support for real-time UI updates
- Health check endpoint for startup validation

Design: All Groq-specific logic is encapsulated here.
Services never import groq directly.
"""

from __future__ import annotations

import time
from typing import AsyncIterator, Optional

from groq import AsyncGroq, Groq
from groq import APIConnectionError, APIStatusError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.logging_config import get_logger
from config.settings import get_settings
from core.interfaces.llm_provider import (
    BaseLLMProvider,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
)

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors that warrant a retry."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIConnectionError):
        return True
    if isinstance(exc, APIStatusError):
        # 429 rate limit, 500/502/503 server errors are retryable
        return exc.status_code in (429, 500, 502, 503)
    return False


class GroqProvider(BaseLLMProvider):
    """
    Groq API provider implementing BaseLLMProvider.

    Wraps the official groq-python SDK. Uses tenacity for retry logic
    so callers never see transient network failures.

    Usage:
        provider = GroqProvider()
        response = provider.generate([
            LLMMessage(role="system", content="You are an expert recruiter."),
            LLMMessage(role="user", content="Analyze this resume: ..."),
        ])
        print(response.content)
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings.llm
        api_key = self._settings.groq_api_key.get_secret_value()
        timeout = float(self._settings.llm_timeout)
        self._client = Groq(api_key=api_key, timeout=timeout, max_retries=1)
        self._async_client = AsyncGroq(api_key=api_key, timeout=timeout, max_retries=1)
        logger.info(
            "GroqProvider initialised",
            extra={"model": self._settings.groq_model},
        )

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a completion with automatic retry on transient errors.

        Args:
            messages: Conversation turns to send to the model.
            temperature: Overrides settings.llm.llm_temperature if provided.
            max_tokens: Overrides settings.llm.llm_max_tokens if provided.

        Returns:
            LLMResponse with content and token usage.

        Raises:
            LLMProviderError: After all retries are exhausted.
        """
        return self._generate_with_retry(messages, temperature, max_tokens)

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Stream response tokens for real-time display in the Streamlit UI.

        Args:
            messages: Conversation turns.
            temperature: Optional temperature override.
            max_tokens: Optional max tokens override.

        Yields:
            String chunks as they arrive from the API.

        Raises:
            LLMProviderError: On API failure.
        """
        groq_messages = self._to_groq_format(messages)
        try:
            async with self._async_client.chat.completions.stream(
                model=self._settings.groq_model,
                messages=groq_messages,
                temperature=temperature or self._settings.llm_temperature,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                **self._reasoning_kwargs(),
            ) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
        except (APIConnectionError, APIStatusError, RateLimitError) as e:
            raise LLMProviderError(
                message=str(e),
                provider=self.provider_name,
                status_code=getattr(e, "status_code", None),
            ) from e

    def health_check(self) -> bool:
        """
        Verify the Groq API is reachable with the configured key.

        Sends a minimal prompt to avoid unnecessary token consumption.
        Called once at application startup.

        Returns:
            True if the API responds successfully.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._settings.groq_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            logger.info("Groq health check passed")
            return True
        except Exception as e:
            logger.error("Groq health check failed", extra={"error": str(e)})
            return False

    def _reasoning_kwargs(self, model: str | None = None) -> dict:
        """
        Cap hidden reasoning for gpt-oss models.

        Reasoning tokens count against max_tokens, so at default effort a
        structured-JSON reply can be truncated before it finishes.
        """
        if "gpt-oss" in (model or self._settings.groq_model):
            return {"reasoning_effort": "low"}
        return {}

    @property
    def provider_name(self) -> str:
        return "Groq"

    @property
    def model_name(self) -> str:
        return self._settings.groq_model

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @retry(
        retry=retry_if_exception_type((APIConnectionError, RateLimitError, APIStatusError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def _generate_with_retry(
        self,
        messages: list[LLMMessage],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> LLMResponse:
        """Internal generate call wrapped with retry logic."""
        groq_messages = self._to_groq_format(messages)
        start = time.perf_counter()

        def _create(model: str):
            return self._client.chat.completions.create(
                model=model,
                messages=groq_messages,
                temperature=temperature or self._settings.llm_temperature,
                max_tokens=max_tokens or self._settings.llm_max_tokens,
                **self._reasoning_kwargs(model),
            )

        try:
            try:
                completion = _create(self._settings.groq_model)
            except RateLimitError:
                # Each Groq model has its own free-tier quota, so a smaller model
                # can keep the app responsive while the primary is rate-limited.
                fallback = self._settings.groq_fallback_model
                if not fallback or fallback == self._settings.groq_model:
                    raise
                logger.warning(
                    "Primary model rate-limited — using fallback model",
                    extra={"primary": self._settings.groq_model, "fallback": fallback},
                )
                completion = _create(fallback)
        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.warning(
                "Groq API error — will retry",
                extra={"error": str(e), "type": type(e).__name__},
            )
            raise  # tenacity catches this and retries
        except Exception as e:
            # Non-retryable error — wrap and raise immediately
            raise LLMProviderError(
                message=str(e),
                provider=self.provider_name,
            ) from e

        elapsed = time.perf_counter() - start
        usage = completion.usage

        response = LLMResponse(
            content=completion.choices[0].message.content or "",
            model=completion.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            finish_reason=completion.choices[0].finish_reason or "stop",
        )

        logger.debug(
            "Groq completion received",
            extra={
                "model": response.model,
                "tokens": response.total_tokens,
                "elapsed_s": round(elapsed, 2),
            },
        )

        return response

    @staticmethod
    def _to_groq_format(messages: list[LLMMessage]) -> list[dict]:
        """Convert LLMMessage dataclasses to Groq API dict format."""
        return [{"role": m.role, "content": m.content} for m in messages]
