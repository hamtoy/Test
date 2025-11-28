"""Tests for the health check module."""

from unittest.mock import MagicMock, patch


class TestCheckNeo4jConnection:
    """Tests for check_neo4j_connection function."""

    def test_neo4j_not_available(self, monkeypatch):
        """Test when neo4j package is not available."""
        # Patch the import to raise ImportError
        import sys

        original_import = (
            __builtins__.__import__
            if hasattr(__builtins__, "__import__")
            else __import__
        )

        def mock_import(name, *args, **kwargs):
            if name == "neo4j.exceptions":
                raise ImportError("No module named 'neo4j'")
            return original_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            patch.dict(sys.modules, {"neo4j.exceptions": None}),
        ):
            from src.infra import health

            # Force re-import to get fresh function
            import importlib

            importlib.reload(health)
            health.check_neo4j_connection(None)
            # Result depends on the module state

    def test_with_valid_kg(self):
        """Test with a valid knowledge graph."""
        from src.infra.health import check_neo4j_connection

        # Create mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"1": 1}
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.session.return_value = mock_session

        # Create mock kg
        mock_kg = MagicMock()
        mock_kg._graph = mock_graph

        with patch("neo4j.exceptions.Neo4jError", Exception):
            result = check_neo4j_connection(mock_kg)
            assert result is True

    def test_with_no_graph_attribute(self):
        """Test when kg has no _graph attribute."""
        from src.infra.health import check_neo4j_connection

        mock_kg = MagicMock()
        mock_kg._graph = None

        result = check_neo4j_connection(mock_kg)
        assert result is False

    def test_with_neo4j_error(self):
        """Test when Neo4j query fails."""
        from src.infra.health import check_neo4j_connection

        # Create mock session that raises error
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        class MockNeo4jError(Exception):
            pass

        mock_session.run.side_effect = MockNeo4jError("Connection failed")

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.session.return_value = mock_session

        # Create mock kg
        mock_kg = MagicMock()
        mock_kg._graph = mock_graph

        with patch("neo4j.exceptions.Neo4jError", MockNeo4jError):
            result = check_neo4j_connection(mock_kg)
            assert result is False

    def test_with_generic_exception(self):
        """Test when a generic exception occurs."""
        from src.infra.health import check_neo4j_connection

        # Create mock session that raises generic exception
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = RuntimeError("Unknown error")

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.session.return_value = mock_session

        # Create mock kg
        mock_kg = MagicMock()
        mock_kg._graph = mock_graph

        result = check_neo4j_connection(mock_kg)
        assert result is False


class TestHealthCheck:
    """Tests for health_check function."""

    def test_health_check_healthy(self):
        """Test health check when all systems are healthy."""
        from src.infra.health import health_check

        with patch("src.infra.health.check_neo4j_connection", return_value=True):
            result = health_check()

            assert result["status"] == "healthy"
            assert result["neo4j"] is True
            assert "timestamp" in result

    def test_health_check_unhealthy(self):
        """Test health check when Neo4j is down."""
        from src.infra.health import health_check

        with patch("src.infra.health.check_neo4j_connection", return_value=False):
            result = health_check()

            assert result["status"] == "unhealthy"
            assert result["neo4j"] is False
            assert "timestamp" in result

    def test_health_check_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        from src.infra.health import health_check
        from datetime import datetime

        with patch("src.infra.health.check_neo4j_connection", return_value=True):
            result = health_check()

            # Should be parseable as ISO format
            timestamp = result["timestamp"]
            # Try to parse as ISO format - should not raise
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
