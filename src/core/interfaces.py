from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
        """Initialize the provider error.

        Args:
            message: The error message.
            original_error: The original exception that caused this error.
        """
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
        """Generates content asynchronously.

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

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Counts tokens for the given text.

        Returns:
            Number of tokens.
        """


class GraphProvider(ABC):
    """Abstract base class for Graph Database providers."""

    @abstractmethod
    def session(self) -> Any:
        """Returns an async context manager for a database session.
        Usage:
            async with provider.session() as session:
                await session.run(...)
        """

    @abstractmethod
    async def close(self) -> None:
        """Closes the provider connection."""

    @abstractmethod
    async def verify_connectivity(self) -> None:
        """Verifies connection to the database."""

    @abstractmethod
    async def create_nodes(
        self,
        nodes: List[Dict[str, Any]],
        label: str,
        merge_on: str = "id",
        merge_keys: Optional[List[str]] = None,
    ) -> int:
        """Batch create or merge nodes.

        Args:
            nodes: List of node property dictionaries.
            label: Node label (e.g., "Person", "Organization").
            merge_on: Primary key for MERGE operation (default: "id").
            merge_keys: Additional keys for merge matching.

        Returns:
            Number of nodes created or merged.
        """

    @abstractmethod
    async def create_relationships(
        self,
        rels: List[Dict[str, Any]],
        rel_type: str,
        from_label: str,
        to_label: str,
        from_key: str = "id",
        to_key: str = "id",
    ) -> int:
        """Batch create relationships between nodes.

        Args:
            rels: List of relationship dictionaries containing
                  'from_id', 'to_id', and optional properties.
            rel_type: Relationship type (e.g., "WORKS_AT", "REFERENCES").
            from_label: Label of the source node.
            to_label: Label of the target node.
            from_key: Key to match source node (default: "id").
            to_key: Key to match target node (default: "id").

        Returns:
            Number of relationships created.
        """
