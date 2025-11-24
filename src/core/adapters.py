from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfigDict
from neo4j import AsyncGraphDatabase

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

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini implementation of LLMProvider."""

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self._model = genai.GenerativeModel(model_name)

    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        response_schema: Optional[Any] = None,
        **kwargs: Any,
    ) -> GenerationResult:
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
                self.model_name, system_instruction=system_instruction
            )

        try:
            response = await model.generate_content_async(
                prompt, generation_config=generation_config, **kwargs
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
                        f"Generation blocked: {finish_reason} ({safety_info})"
                    )

            return GenerationResult(
                content=getattr(response, "text", "") or "",
                usage=usage,
                finish_reason=finish_reason,
                raw_response=response,
            )

        except ProviderError:
            raise
        except google_exceptions.ResourceExhausted as e:
            raise RateLimitError("Gemini rate limit exceeded", original_error=e) from e
        except google_exceptions.InvalidArgument as e:
            if "token" in str(e).lower():
                raise ContextWindowExceededError(
                    "Context window exceeded", original_error=e
                ) from e
            raise ProviderError(f"Invalid argument: {e}", original_error=e) from e
        except google_exceptions.DeadlineExceeded as e:
            raise TimeoutError("Gemini request timed out", original_error=e) from e
        except Exception as e:
            raise ProviderError(
                f"Gemini generation failed: {e}", original_error=e
            ) from e

    async def count_tokens(self, text: str) -> int:
        try:
            return self._model.count_tokens(text).total_tokens
        except Exception as e:
            logger.error(f"Failed to count tokens: {e}")
            # Fallback or re-raise? For now, re-raise as ProviderError
            raise ProviderError(f"Token counting failed: {e}", original_error=e) from e


class Neo4jProvider(GraphProvider):
    """Neo4j implementation of GraphProvider using AsyncGraphDatabase."""

    def __init__(self, uri: str, auth: tuple[str, str]):
        self._driver = AsyncGraphDatabase.driver(uri, auth=auth)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        """
        Yields an async session.
        Enforces explicit transaction scope via async context manager.
        """
        async with self._driver.session() as session:
            yield session

    async def close(self) -> None:
        await self._driver.close()

    async def verify_connectivity(self) -> None:
        try:
            await self._driver.verify_connectivity()
        except Exception as e:
            raise ProviderError(
                f"Neo4j connectivity check failed: {e}", original_error=e
            ) from e
