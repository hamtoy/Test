from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class GenerationResult:
    """Standardized result from LLM generation."""

    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    # Expected keys in usage: "prompt_tokens", "completion_tokens", "total_tokens"
    finish_reason: Optional[str] = None
    safety_ratings: Optional[Dict[str, Any]] = None
    raw_response: Optional[Any] = None  # For debugging purposes


class ProviderError(Exception):
    """Base exception for all provider errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class RateLimitError(ProviderError):
    """Raised when the provider's rate limit is exceeded."""


class ContextWindowExceededError(ProviderError):
    """Raised when the input exceeds the provider's context window."""


class SafetyBlockedError(ProviderError):
    """Raised when the generation is blocked by safety settings."""


class TimeoutError(ProviderError):
    """Raised when the request times out."""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        response_schema: Optional[Any] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """
        Generates content asynchronously.

        Args:
            prompt: The user prompt.
            system_instruction: Optional system instruction.
            temperature: Generation temperature.
            max_output_tokens: Max tokens to generate.
            response_schema: Optional schema for structured output (e.g., Pydantic model or dict).
            **kwargs: Provider-specific arguments.

        Returns:
            GenerationResult object.

        Raises:
            ProviderError: For any provider-related errors.
        """
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """
        Counts tokens for the given text.

        Returns:
            Number of tokens.
        """
        pass


class GraphProvider(ABC):
    """Abstract base class for Graph Database providers."""

    @abstractmethod
    def session(self) -> Any:
        """
        Returns an async context manager for a database session.
        Usage:
            async with provider.session() as session:
                await session.run(...)
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the provider connection."""
        pass

    @abstractmethod
    async def verify_connectivity(self) -> None:
        """Verifies connection to the database."""
        pass
