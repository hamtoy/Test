"""Neo4j connection management module.

Provides connection pooling, health checks, and graceful shutdown
for Neo4j database connections used in the RAG system.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
            from neo4j import GraphDatabase

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
