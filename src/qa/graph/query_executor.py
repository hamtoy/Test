"""Query execution utilities for Neo4j graph operations.

Provides helper functions for executing Cypher queries with proper
async/sync handling and error management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.infra.utils import run_async_safely

logger = logging.getLogger(__name__)


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
        graph_driver: Optional[Any] = None,
        graph_provider: Optional[Any] = None,
    ) -> None:
        """Initialize the query executor."""
        self._graph = graph_driver
        self._graph_provider = graph_provider

    def execute(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
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

        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, **params)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    def execute_write(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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

        async def _run() -> Dict[str, Any]:
            async with prov.session() as session:
                await session.run(cypher, **params)
                # Async providers may have different summary handling
                return {"executed": True}

        return run_async_safely(_run())
