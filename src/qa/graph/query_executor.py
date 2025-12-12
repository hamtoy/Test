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
        transform_fn = self._resolve_transform(transform)

        no_result = object()
        sync_result = self._try_execute_sync(
            cypher,
            params,
            transform_fn,
            no_result,
        )
        if sync_result is not no_result:
            return cast("T | list[dict[str, Any]]", sync_result)

        return self._execute_async_fallback(cypher, params, default, transform_fn)

    def _resolve_transform(
        self,
        transform: Callable[[list[Any]], T] | None,
    ) -> Callable[[list[Any]], T | list[dict[str, Any]]]:
        if transform is not None:
            return transform

        def default_transform(records: list[Any]) -> list[dict[str, Any]]:
            return [dict(r) for r in records]

        return cast(
            "Callable[[list[Any]], T | list[dict[str, Any]]]",
            default_transform,
        )

    def _try_execute_sync(
        self,
        cypher: str,
        params: dict[str, Any],
        transform_fn: Callable[[list[Any]], T | list[dict[str, Any]]],
        no_result: object,
    ) -> T | list[dict[str, Any]] | object:
        if self._graph is None:
            return no_result
        try:
            with self._graph.session() as session:
                records = session.run(cypher, **params)
                return transform_fn(records)
        except (Neo4jError, ServiceUnavailable) as exc:
            logger.warning("Sync query failed: %s", exc)
            return no_result

    def _execute_async_fallback(
        self,
        cypher: str,
        params: dict[str, Any],
        default: T | None,
        transform_fn: Callable[[list[Any]], T | list[dict[str, Any]]],
    ) -> T | list[dict[str, Any]]:
        if self._graph_provider is None:
            logger.warning("No graph provider available")
            return default if default is not None else []

        prov = self._graph_provider

        async def _run() -> T | list[dict[str, Any]]:
            try:
                async with prov.session() as session:
                    result = await session.run(cypher, **params)
                    records = (
                        [record async for record in result]
                        if hasattr(result, "__aiter__")
                        else list(result)
                    )
                    return transform_fn(records)
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Async query failed: %s", exc)
                return default if default is not None else []

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
