"""Query execution utilities for Neo4j graph operations.

Provides helper functions for executing Cypher queries with proper
async/sync handling and error management.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.infra.utils import run_async_safely

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryExecutor:
    """Executes Cypher queries against Neo4j with async support.

    Provides a unified interface for executing queries regardless of
    whether a sync driver or async graph provider is being used.

    Args:
        graph_driver: Sync Neo4j driver instance
        graph_provider: Async graph provider instance (optional)
    """

    def __init__(
        self,
        graph_driver: Any | None = None,
        graph_provider: Any | None = None,
    ) -> None:
        """Initialize the query executor."""
        self._graph = graph_driver
        self._graph_provider = graph_provider

    def execute(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.

        Args:
            cypher: The Cypher query string
            params: Query parameters

        Returns:
            List of result records as dictionaries
        """
        params = params or {}

        if self._graph_provider is None:
            if self._graph is None:
                raise RuntimeError("No graph driver or provider available")
            with self._graph.session() as session:
                records = session.run(cypher, **params)
                return [dict(r) for r in records]

        prov = self._graph_provider

        async def _run() -> list[dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, **params)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    def execute_with_fallback(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        default: T | None = None,
        transform: Callable[[list[Any]], T] | None = None,
    ) -> T | list[dict[str, Any]]:
        """Execute query with sync-first, async-fallback pattern.

        Tries sync driver first, falls back to async provider if sync fails.
        Commonly used pattern in rag_system.py.

        Args:
            cypher: The Cypher query string
            params: Query parameters
            default: Default value if both sync and async fail
            transform: Optional function to transform result records

        Returns:
            Transformed result or default value
        """
        params = params or {}

        def default_transform(records: list[Any]) -> list[dict[str, Any]]:
            return [dict(r) for r in records]

        transform_fn: Callable[[list[Any]], T | list[dict[str, Any]]]
        if transform is not None:
            transform_fn = transform
        else:
            transform_fn = cast(
                "Callable[[list[Any]], T | list[dict[str, Any]]]",
                default_transform,
            )

        # Try sync driver first
        if self._graph is not None:
            try:
                with self._graph.session() as session:
                    records = session.run(cypher, **params)
                    return transform_fn(records)
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Sync query failed: %s", exc)

        # Fall back to async provider
        if self._graph_provider is None:
            logger.warning("No graph provider available")
            if default is not None:
                return default
            return []

        prov = self._graph_provider

        async def _run() -> T | list[dict[str, Any]]:
            try:
                async with prov.session() as session:
                    result = await session.run(cypher, **params)
                    if hasattr(result, "__aiter__"):
                        records = [record async for record in result]
                    else:
                        records = list(result)
                    return transform_fn(records)
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Async query failed: %s", exc)
                if default is not None:
                    return default
                return []

        return run_async_safely(_run())

    def execute_write(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write query and return summary.

        Args:
            cypher: The Cypher write query
            params: Query parameters

        Returns:
            Summary of the write operation
        """
        params = params or {}

        if self._graph_provider is None:
            if self._graph is None:
                raise RuntimeError("No graph driver or provider available")
            with self._graph.session() as session:
                result = session.run(cypher, **params)
                summary = result.consume()
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                }

        prov = self._graph_provider

        async def _run() -> dict[str, Any]:
            async with prov.session() as session:
                await session.run(cypher, **params)
                # Async providers may have different summary handling
                return {"executed": True}

        return run_async_safely(_run())
