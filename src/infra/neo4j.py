"""Neo4j 연결 유틸리티 모듈."""

from __future__ import annotations

import atexit
import os
from contextlib import asynccontextmanager, suppress
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase, Driver

from src.core.interfaces import GraphProvider

__all__ = [
    "SafeDriver",
    "create_sync_driver",
    "get_neo4j_driver_from_env",
    "Neo4jGraphProvider",
]


class SafeDriver:
    """Thin wrapper around Neo4j sync Driver that guarantees close is called.

    Supports context manager semantics to encourage explicit lifecycle control.
    """

    def __init__(self, driver: Driver, *, register_atexit: bool = False):
        """Initialize the SafeDriver wrapper.

        Args:
            driver: The Neo4j Driver instance to wrap.
            register_atexit: Whether to register cleanup on program exit.
        """
        self._driver: Optional[Driver] = driver
        self._register_atexit = register_atexit
        if register_atexit:
            atexit.register(self.close)

    @property
    def driver(self) -> Driver:
        """내부 Neo4j Driver 인스턴스에 대한 접근자."""
        if self._driver is None:
            raise RuntimeError("Driver already closed")
        return self._driver

    def session(self, *args: Any, **kwargs: Any) -> Any:
        """Create a new database session."""
        if self._driver is None:
            raise RuntimeError("Driver already closed")
        return self._driver.session(*args, **kwargs)

    def close(self) -> None:
        """Close the database connection."""
        if self._driver is None:
            return
        with suppress(Exception):
            self._driver.close()
        self._driver = None

    def __enter__(self) -> "SafeDriver":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit context manager and close resources."""
        self.close()

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the underlying driver."""
        if self._driver is None:
            raise AttributeError(name)
        return getattr(self._driver, name)

    def __del__(self) -> None:
        """Destructor to ensure resources are cleaned up."""
        self.close()


def create_sync_driver(
    uri: str,
    user: str,
    password: str,
    *,
    register_atexit: bool = False,
    graph_db_factory: Optional[Callable[..., Driver]] = None,
) -> SafeDriver:
    """Create a Neo4j sync driver wrapped with SafeDriver to enforce close().

    PHASE 1: Connection pool optimization for performance improvement.
    - max_connection_pool_size: 50 (handle concurrent requests)
    - connection_acquisition_timeout: 30.0s (prevent hanging)
    - max_connection_lifetime: 3600s (1 hour, refresh connections)
    """
    factory = graph_db_factory or GraphDatabase.driver
    # PHASE 1: Add connection pool configuration for performance
    driver = factory(
        uri,
        auth=(user, password),
        max_connection_pool_size=50,
        connection_acquisition_timeout=30.0,
        max_connection_lifetime=3600,
    )
    return SafeDriver(driver, register_atexit=register_atexit)


def get_neo4j_driver_from_env(*, register_atexit: bool = False) -> SafeDriver:
    """환경 변수에서 Neo4j 연결 정보를 읽어 SafeDriver 생성.

    환경 변수:
        NEO4J_URI: Neo4j 서버 URI
        NEO4J_USER: 사용자 이름
        NEO4J_PASSWORD: 비밀번호

    Raises:
        EnvironmentError: 필수 환경 변수 누락 시

    Returns:
        SafeDriver 인스턴스
    """
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if uri is None or user is None or password is None:
        raise EnvironmentError(
            "Missing required Neo4j environment variables: "
            "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
        )

    return create_sync_driver(uri, user, password, register_atexit=register_atexit)


class Neo4jGraphProvider(GraphProvider):
    """Neo4j implementation of GraphProvider with async support.

    Supports both read operations (session, verify_connectivity) and
    write operations (create_nodes, create_relationships) for Data2Neo pipeline.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        *,
        batch_size: int = 100,
    ) -> None:
        """Initialize Neo4jGraphProvider.

        Args:
            uri: Neo4j server URI (e.g., "bolt://localhost:7687").
            user: Neo4j username.
            password: Neo4j password.
            batch_size: Default batch size for write operations.
        """
        self._uri = uri
        self._user = user
        self._password = password
        self._batch_size = batch_size
        self._driver: Optional[AsyncDriver] = None

    async def _get_driver(self) -> AsyncDriver:
        """Lazily initialize and return the async driver.

        PHASE 1: Connection pool optimization for async operations.
        """
        if self._driver is None:
            # PHASE 1: Add connection pool configuration for performance
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0,
                max_connection_lifetime=3600,
            )
        return self._driver

    @asynccontextmanager
    async def _session_context(self) -> AsyncIterator[Any]:
        """Async context manager for database session."""
        driver = await self._get_driver()
        async with driver.session() as session:
            yield session

    def session(self) -> Any:
        """Returns an async context manager for a database session.

        Usage:
            async with provider.session() as session:
                result = await session.run("MATCH (n) RETURN n LIMIT 10")
        """
        return self._session_context()

    async def close(self) -> None:
        """Closes the provider connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def verify_connectivity(self) -> None:
        """Verifies connection to the database."""
        driver = await self._get_driver()
        await driver.verify_connectivity()

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
