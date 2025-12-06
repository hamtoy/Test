"""Neo4j connection management module.

Provides connection pooling, health checks, graceful shutdown,
and session management for Neo4j database connections used in the RAG system.
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from contextlib import contextmanager, suppress
from typing import Any, Generator, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.config.utils import require_env
from src.core.interfaces import GraphProvider
from src.infra.neo4j import SafeDriver, create_sync_driver

logger = logging.getLogger(__name__)


def initialize_connection(
    neo4j_uri: Optional[str],
    neo4j_user: Optional[str],
    neo4j_password: Optional[str],
    provider: Optional[GraphProvider],
) -> tuple[Optional[SafeDriver], Optional[Any]]:
    """Initialize Neo4j connection with provider support.

    Args:
        neo4j_uri: Neo4j database URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        provider: Optional graph provider

    Returns:
        Tuple of (driver, finalizer)
    """
    graph: Optional[SafeDriver] = None
    finalizer: Optional[Any] = None

    if provider is None:
        # No provider - create direct connection
        uri = neo4j_uri or require_env("NEO4J_URI")
        user = neo4j_user or require_env("NEO4J_USER")
        password = neo4j_password or require_env("NEO4J_PASSWORD")

        try:
            graph = create_sync_driver(
                uri,
                user,
                password,
                register_atexit=True,
                graph_db_factory=GraphDatabase.driver,
            )
            finalizer = weakref.finalize(graph, graph.close)
        except Neo4jError as e:
            raise RuntimeError(f"Neo4j 연결 실패: {e}")
    else:
        # Provider available - use it, but also setup direct connection if credentials exist
        if neo4j_uri and neo4j_user and neo4j_password:
            graph = create_sync_driver(
                neo4j_uri,
                neo4j_user,
                neo4j_password,
                register_atexit=True,
                graph_db_factory=GraphDatabase.driver,
            )
            finalizer = weakref.finalize(graph, graph.close)

    return graph, finalizer


def close_connections(
    graph: Optional[SafeDriver],
    graph_finalizer: Optional[Any],
    graph_provider: Optional[GraphProvider],
) -> None:
    """Close database connections and clean up resources.

    Args:
        graph: Sync driver instance
        graph_finalizer: Weakref finalizer
        graph_provider: Async graph provider
    """
    if graph:
        with suppress(Exception):
            graph.close()

    if graph_finalizer and graph_finalizer.alive:
        with suppress(Exception):
            graph_finalizer()

    if graph_provider:
        try:
            try:
                loop = asyncio.get_running_loop()
                running = True
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                running = False

            close_coro = graph_provider.close()
            if running and loop.is_running():
                loop.create_task(close_coro)
            else:
                loop.run_until_complete(close_coro)
                if not running:
                    loop.close()
                    asyncio.set_event_loop(None)
        except (RuntimeError, Neo4jError, ServiceUnavailable) as exc:
            logger.warning("Graph provider close failed: %s", exc)


def create_graph_session(
    graph: Optional[SafeDriver],
    graph_provider: Optional[GraphProvider],
) -> Generator[Any, None, None]:
    """Create a synchronous Neo4j session.

    Tries sync driver first, falls back to async provider if available.

    Args:
        graph: Sync driver instance
        graph_provider: Async graph provider

    Yields:
        Session instance or None
    """
    if graph:
        with graph.session() as session:
            yield session
        return

    if graph_provider:
        # Synchronize async provider in sync context
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                logger.debug("Event loop running; skipping provider session")
                yield None
                return
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        session_cm = graph_provider.session()
        session = loop.run_until_complete(session_cm.__aenter__())
        try:
            yield session
        finally:
            loop.run_until_complete(session_cm.__aexit__(None, None, None))
            loop.close()
        return

    logger.debug("Graph not available; yielding None")
    yield None


class Neo4jConnectionManager:
    """Manages Neo4j database connections.

    Handles connection lifecycle, health checks, and provides
    a unified interface for database operations.

    Args:
        uri: Neo4j bolt URI (e.g., 'bolt://localhost:7687')
        user: Database username
        password: Database password

    Raises:
        ConnectionError: If unable to establish database connection
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Initialize Neo4j connection manager."""
        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self._driver: Any = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Neo4j database.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if not self.uri or not self.user or not self.password:
                logger.warning("Neo4j connection credentials incomplete")
                return False

            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j connection established: %s", self.uri)
            return True
        except Exception as e:
            logger.warning("Neo4j connection failed: %s", e)
            self._connected = False
            return False

    def close(self) -> None:
        """Close Neo4j connection gracefully."""
        if self._driver:
            self._driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._connected

    @property
    def driver(self) -> Any:
        """Get the Neo4j driver instance."""
        if not self._connected:
            self.connect()
        return self._driver

    def execute_query(
        self, query: str, parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        if not self._driver:
            raise ConnectionError("Not connected to Neo4j")

        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
