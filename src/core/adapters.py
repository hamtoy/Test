# mypy: disable-error-code=attr-defined
"""Provider Adapters module.

Concrete implementations of LLMProvider (GeminiProvider) and GraphProvider (Neo4jProvider).
Handles API-specific error mapping, token counting, and batch operations.
"""

from __future__ import annotations

import logging
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfigDict

from src.core.interfaces import (
    ContextWindowExceededError,
    GenerationResult,
    GraphProvider,
    LLMProvider,
    ProviderError,
    RateLimitError,
    SafetyBlockedError,
    TimeoutError,
)
from src.infra.neo4j import Neo4jGraphProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini implementation of LLMProvider."""

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        """Initialize the Gemini provider.

        Args:
            api_key: The Google AI API key.
            model_name: The Gemini model name to use.
        """
        # API 초기화 (테스트에서 genai.configure 패치 가능)
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self._model = genai.GenerativeModel(model_name)

    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_schema: Any | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate content asynchronously using Gemini.

        Args:
            prompt: The input prompt text.
            system_instruction: Optional system instruction for the model.
            temperature: Sampling temperature for generation.
            max_output_tokens: Maximum number of tokens to generate.
            response_schema: Optional JSON schema for structured output.
            **kwargs: Additional generation configuration options.

        Returns:
            GenerationResult containing the generated content and metadata.

        Raises:
            SafetyBlockedError: If generation is blocked by safety filters.
            RateLimitError: If rate limit is exceeded.
            ContextWindowExceededError: If input exceeds context window.
            TimeoutError: If the request times out.
            ProviderError: For other generation failures.
        """
        generation_config: GenerationConfigDict = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_output_tokens is not None:
            generation_config["max_output_tokens"] = max_output_tokens
        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        # Create a new model instance if system_instruction is provided,
        # as it's set at initialization time for GenerativeModel.
        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                self.model_name,
                system_instruction=system_instruction,
            )

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                **kwargs,
            )

            # Extract usage metadata
            usage = {}
            if hasattr(response, "usage_metadata"):
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                }

            # Extract finish reason and handle safety blocks
            finish_reason = None
            if getattr(response, "candidates", None):
                candidate = response.candidates[0]
                finish_reason = getattr(candidate.finish_reason, "name", None)
                if finish_reason and finish_reason.upper() not in {
                    "STOP",
                    "MAX_TOKENS",
                }:
                    safety_info = getattr(response, "prompt_feedback", None)
                    raise SafetyBlockedError(
                        f"Generation blocked: {finish_reason} ({safety_info})",
                    )

            return GenerationResult(
                content=getattr(response, "text", "") or "",
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response,
            )

        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._convert_google_exception(exc) from exc

    def _convert_google_exception(self, exc: Exception) -> ProviderError:
        if isinstance(exc, google_exceptions.ResourceExhausted):
            return RateLimitError(
                "Gemini rate limit exceeded",
                original_error=exc,
            )
        if isinstance(exc, google_exceptions.InvalidArgument):
            if "token" in str(exc).lower():
                return ContextWindowExceededError(
                    "Context window exceeded",
                    original_error=exc,
                )
            return ProviderError(f"Invalid argument: {exc}", original_error=exc)
        if isinstance(exc, google_exceptions.DeadlineExceeded):
            return TimeoutError("Gemini request timed out", original_error=exc)
        return ProviderError(
            f"Gemini generation failed: {exc}",
            original_error=exc,
        )

    async def count_tokens(self, text: str) -> int:
        """Count tokens in the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens in the text.

        Raises:
            ProviderError: If token counting fails.
        """
        try:
            return int(self._model.count_tokens(text).total_tokens)
        except Exception as e:
            logger.error(f"Failed to count tokens: {e}")
            # Fallback or re-raise? For now, re-raise as ProviderError
            raise ProviderError(f"Token counting failed: {e}", original_error=e) from e


class Neo4jProvider(GraphProvider):
    """Neo4j implementation of GraphProvider delegating to infra layer."""

    def __init__(
        self,
        uri: str,
        auth: tuple[str, str],
        *,
        batch_size: int = 100,
        provider: Neo4jGraphProvider | None = None,
    ):
        """Initialize the Neo4j provider.

        Args:
            uri: The Neo4j database URI.
            auth: A tuple of (username, password) for authentication.
            batch_size: Number of records to process in each batch.
            provider: Optional pre-configured Neo4jGraphProvider for injection.
        """
        if provider is None:
            user, password = auth
            provider = Neo4jGraphProvider(
                uri=uri,
                user=user,
                password=password,
                batch_size=batch_size,
            )

        self._provider = provider

    def session(self) -> Any:
        """Return an async session context manager."""
        return self._provider.session()

    async def close(self) -> None:
        """Close the database connection."""
        await self._provider.close()

    async def verify_connectivity(self) -> None:
        """Verify that the database connection is working."""
        try:
            await self._provider.verify_connectivity()
        except Exception as e:
            raise ProviderError(
                f"Neo4j connectivity check failed: {e}",
                original_error=e,
            ) from e

    async def create_nodes(
        self,
        nodes: list[dict[str, Any]],
        label: str,
        merge_on: str = "id",
        merge_keys: list[str] | None = None,
    ) -> int:
        """Batch create or merge nodes using the shared provider implementation."""
        return await self._provider.create_nodes(
            nodes,
            label,
            merge_on,
            merge_keys,
        )

    async def create_relationships(
        self,
        rels: list[dict[str, Any]],
        rel_type: str,
        from_label: str,
        to_label: str,
        from_key: str = "id",
        to_key: str = "id",
    ) -> int:
        """Batch create relationships using the shared provider implementation."""
        return await self._provider.create_relationships(
            rels,
            rel_type,
            from_label,
            to_label,
            from_key,
            to_key,
        )
