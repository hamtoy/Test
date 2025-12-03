# mypy: disable-error-code=attr-defined
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

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
        """Initialize the Gemini provider.

        Args:
            api_key: The Google AI API key.
            model_name: The Gemini model name to use.
        """
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
    """Neo4j implementation of GraphProvider using AsyncGraphDatabase."""

    def __init__(self, uri: str, auth: tuple[str, str], *, batch_size: int = 100):
        """Initialize the Neo4j provider.

        Args:
            uri: The Neo4j database URI.
            auth: A tuple of (username, password) for authentication.
            batch_size: Number of records to process in each batch.
        """
        self._driver = AsyncGraphDatabase.driver(uri, auth=auth)
        self._batch_size = batch_size

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        """Yields an async session.

        Enforces explicit transaction scope via async context manager.
        """
        async with self._driver.session() as session:
            yield session

    async def close(self) -> None:
        """Close the database connection."""
        await self._driver.close()

    async def verify_connectivity(self) -> None:
        """Verify that the database connection is working.

        Raises:
            ProviderError: If connectivity check fails.
        """
        try:
            await self._driver.verify_connectivity()
        except Exception as e:
            raise ProviderError(
                f"Neo4j connectivity check failed: {e}", original_error=e
            ) from e

    async def create_nodes(
        self,
        nodes: List[Dict[str, Any]],
        label: str,
        merge_on: str = "id",
        merge_keys: Optional[List[str]] = None,
    ) -> int:
        """Batch create or merge nodes using UNWIND for efficiency.

        Args:
            nodes: List of node property dictionaries. All nodes should have
                   the same property keys for consistent schema handling.
            label: Node label (e.g., "Person", "Organization").
            merge_on: Primary key for MERGE operation (default: "id").
            merge_keys: Additional keys for merge matching.

        Returns:
            Number of nodes created or merged.

        Note:
            This method assumes all nodes in the list have consistent property
            keys. The first node's keys are used to build the SET clause.
        """
        if not nodes:
            return 0

        # Build merge keys
        keys = [merge_on] + (merge_keys or [])
        merge_clause = ", ".join(f"{k}: node.{k}" for k in keys)

        # Build SET clause for remaining properties
        set_props = [k for k in nodes[0] if k not in keys]
        set_clause = ", ".join(f"n.{k} = node.{k}" for k in set_props)

        query = f"""
        UNWIND $nodes AS node
        MERGE (n:{label} {{{merge_clause}}})
        """
        if set_clause:
            query += f"SET {set_clause}\n"
        query += "RETURN count(n) AS count"

        total_count = 0
        async with self.session() as session:
            # Process in batches
            for i in range(0, len(nodes), self._batch_size):
                batch = nodes[i : i + self._batch_size]
                result = await session.run(query, nodes=batch)
                record = await result.single()
                if record:
                    total_count += record["count"]

        return total_count

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
                  'from_id', 'to_id', and optional properties. All relationships
                  should have the same property keys for consistent schema handling.
            rel_type: Relationship type (e.g., "WORKS_AT", "REFERENCES").
            from_label: Label of the source node.
            to_label: Label of the target node.
            from_key: Key to match source node (default: "id").
            to_key: Key to match target node (default: "id").

        Returns:
            Number of relationships created.

        Note:
            This method assumes all relationships in the list have consistent
            property keys. The first relationship's keys are used to build
            the property clause.
        """
        if not rels:
            return 0

        # Extract property keys (excluding from_id and to_id)
        prop_keys = [k for k in rels[0] if k not in ("from_id", "to_id")]
        props_clause = ", ".join(f"{k}: rel.{k}" for k in prop_keys)

        query = f"""
        UNWIND $rels AS rel
        MATCH (a:{from_label} {{{from_key}: rel.from_id}})
        MATCH (b:{to_label} {{{to_key}: rel.to_id}})
        MERGE (a)-[r:{rel_type}"""

        if props_clause:
            query += f" {{{props_clause}}}"
        query += """]->(b)
        RETURN count(r) AS count"""

        total_count = 0
        async with self.session() as session:
            # Process in batches
            for i in range(0, len(rels), self._batch_size):
                batch = rels[i : i + self._batch_size]
                result = await session.run(query, rels=batch)
                record = await result.single()
                if record:
                    total_count += record["count"]

        return total_count
