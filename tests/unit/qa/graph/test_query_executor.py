"""Tests for query execution utilities module."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.qa.graph.query_executor import QueryExecutor


class TestQueryExecutor:
    """Tests for QueryExecutor class."""

    def test_init_with_driver(self) -> None:
        """Test initialization with sync driver."""
        mock_driver = MagicMock()
        executor = QueryExecutor(graph_driver=mock_driver)

        assert executor._graph is mock_driver
        assert executor._graph_provider is None

    def test_init_with_provider(self) -> None:
        """Test initialization with async provider."""
        mock_provider = MagicMock()
        executor = QueryExecutor(graph_provider=mock_provider)

        assert executor._graph is None
        assert executor._graph_provider is mock_provider

    def test_init_with_both(self) -> None:
        """Test initialization with both driver and provider."""
        mock_driver = MagicMock()
        mock_provider = MagicMock()
        executor = QueryExecutor(
            graph_driver=mock_driver,
            graph_provider=mock_provider,
        )

        assert executor._graph is mock_driver
        assert executor._graph_provider is mock_provider

    def test_execute_with_driver(self) -> None:
        """Test query execution using sync driver."""
        mock_record1 = {"id": 1, "name": "test1"}
        mock_record2 = {"id": 2, "name": "test2"}

        mock_session = MagicMock()
        mock_session.run.return_value = [mock_record1, mock_record2]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        executor = QueryExecutor(graph_driver=mock_driver)
        results = executor.execute("MATCH (n) RETURN n", {"limit": 10})

        assert results == [mock_record1, mock_record2]
        mock_session.run.assert_called_once()

    def test_execute_with_default_params(self) -> None:
        """Test query execution with default empty params."""
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        executor = QueryExecutor(graph_driver=mock_driver)
        results = executor.execute("MATCH (n) RETURN n")

        assert results == []

    def test_execute_no_driver_or_provider(self) -> None:
        """Test execute raises when no driver or provider available."""
        executor = QueryExecutor()

        with pytest.raises(RuntimeError, match="No graph driver or provider available"):
            executor.execute("MATCH (n) RETURN n")

    def test_execute_write_with_driver(self) -> None:
        """Test write query execution using sync driver."""
        mock_summary = MagicMock()
        mock_summary.counters.nodes_created = 1
        mock_summary.counters.nodes_deleted = 0
        mock_summary.counters.relationships_created = 2
        mock_summary.counters.properties_set = 3

        mock_result = MagicMock()
        mock_result.consume.return_value = mock_summary

        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        executor = QueryExecutor(graph_driver=mock_driver)
        result = executor.execute_write(
            "CREATE (n:Node {name: $name})",
            {"name": "test"},
        )

        assert result["nodes_created"] == 1
        assert result["nodes_deleted"] == 0
        assert result["relationships_created"] == 2
        assert result["properties_set"] == 3

    def test_execute_write_with_default_params(self) -> None:
        """Test write query execution with default empty params."""
        mock_summary = MagicMock()
        mock_summary.counters.nodes_created = 0
        mock_summary.counters.nodes_deleted = 1
        mock_summary.counters.relationships_created = 0
        mock_summary.counters.properties_set = 0

        mock_result = MagicMock()
        mock_result.consume.return_value = mock_summary

        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        executor = QueryExecutor(graph_driver=mock_driver)
        result = executor.execute_write("MATCH (n) DETACH DELETE n")

        assert result["nodes_deleted"] == 1

    def test_execute_write_no_driver_or_provider(self) -> None:
        """Test execute_write raises when no driver or provider available."""
        executor = QueryExecutor()

        with pytest.raises(RuntimeError, match="No graph driver or provider available"):
            executor.execute_write("CREATE (n:Node)")


class TestQueryExecutorWithAsyncProvider:
    """Tests for QueryExecutor with async provider."""

    def test_execute_with_async_provider(self) -> None:
        """Test query execution using async provider."""
        mock_records = [{"id": 1}, {"id": 2}]

        # Create an async mock session
        mock_async_session = MagicMock()
        mock_async_session.run = AsyncMock(return_value=mock_records)

        # Create async context manager for session
        mock_provider = MagicMock()

        class AsyncSessionContext:
            async def __aenter__(self) -> MagicMock:
                return mock_async_session

            async def __aexit__(
                self,
                exc_type: Any,
                exc_val: Any,
                exc_tb: Any,
            ) -> None:
                pass

        mock_provider.session.return_value = AsyncSessionContext()

        executor = QueryExecutor(graph_provider=mock_provider)
        results = executor.execute("MATCH (n) RETURN n", {"limit": 5})

        assert results == mock_records

    def test_execute_write_with_async_provider(self) -> None:
        """Test write query execution using async provider."""
        # Create an async mock session
        mock_async_session = MagicMock()
        mock_async_session.run = AsyncMock(return_value=None)

        # Create async context manager for session
        mock_provider = MagicMock()

        class AsyncSessionContext:
            async def __aenter__(self) -> MagicMock:
                return mock_async_session

            async def __aexit__(
                self,
                exc_type: Any,
                exc_val: Any,
                exc_tb: Any,
            ) -> None:
                pass

        mock_provider.session.return_value = AsyncSessionContext()

        executor = QueryExecutor(graph_provider=mock_provider)
        result = executor.execute_write("CREATE (n:Node)")

        assert result == {"executed": True}


class TestQueryExecutorWithFallback:
    def test_execute_with_fallback_returns_default_when_no_provider(self) -> None:
        executor = QueryExecutor()
        assert executor.execute_with_fallback(
            "MATCH (n) RETURN n", default={"x": 1}
        ) == {
            "x": 1,
        }
        assert executor.execute_with_fallback("MATCH (n) RETURN n") == []

    def test_execute_with_fallback_uses_async_provider_on_sync_error(self) -> None:
        from neo4j.exceptions import Neo4jError

        mock_session = MagicMock()
        mock_session.run.side_effect = Neo4jError("boom")
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        mock_async_session = MagicMock()
        mock_async_session.run = AsyncMock(return_value=[{"id": 1}])

        class _AsyncCtx:
            async def __aenter__(self):  # noqa: ANN001
                return mock_async_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
                return None

        mock_provider = MagicMock()
        mock_provider.session.return_value = _AsyncCtx()

        executor = QueryExecutor(graph_driver=mock_driver, graph_provider=mock_provider)
        assert executor.execute_with_fallback("MATCH (n) RETURN n") == [{"id": 1}]
