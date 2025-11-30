"""Tests for Neo4j connection management module."""

from unittest.mock import MagicMock, patch

import pytest

from src.qa.graph.connection import Neo4jConnectionManager


class TestNeo4jConnectionManager:
    """Tests for Neo4jConnectionManager class."""

    def test_init_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with default environment variables."""
        monkeypatch.setenv("NEO4J_URI", "bolt://test:7687")
        monkeypatch.setenv("NEO4J_USER", "testuser")
        monkeypatch.setenv("NEO4J_PASSWORD", "testpass")

        manager = Neo4jConnectionManager()

        assert manager.uri == "bolt://test:7687"
        assert manager.user == "testuser"
        assert manager.password == "testpass"
        assert manager._driver is None
        assert manager._connected is False

    def test_init_with_parameters(self) -> None:
        """Test initialization with explicit parameters."""
        manager = Neo4jConnectionManager(
            uri="bolt://custom:7687",
            user="customuser",
            password="custompass",
        )

        assert manager.uri == "bolt://custom:7687"
        assert manager.user == "customuser"
        assert manager.password == "custompass"

    def test_is_connected_property(self) -> None:
        """Test is_connected property."""
        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )

        assert manager.is_connected is False

        manager._connected = True
        assert manager.is_connected is True

    def test_connect_success(self) -> None:
        """Test successful connection to Neo4j."""
        mock_driver = MagicMock()
        mock_driver.verify_connectivity.return_value = None

        with (
            patch.dict("sys.modules", {"neo4j": MagicMock()}),
            patch("neo4j.GraphDatabase") as mock_gd,
        ):
            mock_gd.driver.return_value = mock_driver

            manager = Neo4jConnectionManager(
                uri="bolt://test:7687",
                user="user",
                password="pass",
            )

            result = manager.connect()

            assert result is True
            assert manager.is_connected is True
            assert manager._driver is mock_driver
            mock_gd.driver.assert_called_once_with(
                "bolt://test:7687",
                auth=("user", "pass"),
            )
            mock_driver.verify_connectivity.assert_called_once()

    def test_connect_missing_credentials(self) -> None:
        """Test connection fails with missing credentials."""
        manager = Neo4jConnectionManager(
            uri="",  # Empty URI
            user="user",
            password="pass",
        )

        result = manager.connect()

        assert result is False
        assert manager.is_connected is False

    def test_connect_failure(self) -> None:
        """Test connection handles exceptions gracefully."""
        with (
            patch.dict("sys.modules", {"neo4j": MagicMock()}),
            patch("neo4j.GraphDatabase") as mock_gd,
        ):
            mock_gd.driver.side_effect = Exception("Connection failed")

            manager = Neo4jConnectionManager(
                uri="bolt://test:7687",
                user="user",
                password="pass",
            )

            result = manager.connect()

            assert result is False
            assert manager.is_connected is False

    def test_close(self) -> None:
        """Test closing connection."""
        mock_driver = MagicMock()

        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )
        manager._driver = mock_driver
        manager._connected = True

        manager.close()

        mock_driver.close.assert_called_once()
        assert manager.is_connected is False

    def test_close_no_driver(self) -> None:
        """Test closing when no driver exists."""
        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )

        # Should not raise
        manager.close()

    def test_driver_property_when_not_connected(self) -> None:
        """Test driver property triggers connect when not connected."""
        mock_driver = MagicMock()
        mock_driver.verify_connectivity.return_value = None

        with (
            patch.dict("sys.modules", {"neo4j": MagicMock()}),
            patch("neo4j.GraphDatabase") as mock_gd,
        ):
            mock_gd.driver.return_value = mock_driver

            manager = Neo4jConnectionManager(
                uri="bolt://test:7687",
                user="user",
                password="pass",
            )

            # Accessing driver should trigger connect
            driver = manager.driver

            assert driver is mock_driver
            assert manager.is_connected is True

    def test_driver_property_when_connected(self) -> None:
        """Test driver property returns cached driver when connected."""
        mock_driver = MagicMock()

        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )
        manager._driver = mock_driver
        manager._connected = True

        driver = manager.driver

        assert driver is mock_driver

    def test_execute_query_success(self) -> None:
        """Test successful query execution."""
        mock_record1 = MagicMock()
        mock_record1.data.return_value = {"id": 1, "name": "test1"}
        mock_record2 = MagicMock()
        mock_record2.data.return_value = {"id": 2, "name": "test2"}

        mock_result = [mock_record1, mock_record2]
        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )
        manager._driver = mock_driver

        results = manager.execute_query(
            "MATCH (n) RETURN n.id, n.name",
            {"limit": 10},
        )

        assert results == [
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"},
        ]
        mock_session.run.assert_called_once_with(
            "MATCH (n) RETURN n.id, n.name", {"limit": 10}
        )

    def test_execute_query_no_parameters(self) -> None:
        """Test query execution without parameters."""
        mock_record = MagicMock()
        mock_record.data.return_value = {"count": 42}

        mock_result = [mock_record]
        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )
        manager._driver = mock_driver

        results = manager.execute_query("MATCH (n) RETURN count(n) as count")

        assert results == [{"count": 42}]
        mock_session.run.assert_called_once_with(
            "MATCH (n) RETURN count(n) as count", {}
        )

    def test_execute_query_not_connected(self) -> None:
        """Test query execution raises when not connected."""
        manager = Neo4jConnectionManager(
            uri="bolt://test:7687",
            user="user",
            password="pass",
        )

        with pytest.raises(ConnectionError, match="Not connected to Neo4j"):
            manager.execute_query("MATCH (n) RETURN n")
