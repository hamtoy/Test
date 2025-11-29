"""Tests for Neo4jGraphProvider write operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.infra.neo4j import Neo4jGraphProvider


class TestNeo4jGraphProviderInit:
    """Test Neo4jGraphProvider initialization."""

    def test_init_stores_credentials(self) -> None:
        """Provider stores connection credentials."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
            batch_size=50,
        )
        assert provider._uri == "bolt://localhost:7687"
        assert provider._user == "neo4j"
        assert provider._password == "password"
        assert provider._batch_size == 50
        assert provider._driver is None

    def test_init_default_batch_size(self) -> None:
        """Provider uses default batch size of 100."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )
        assert provider._batch_size == 100


class TestNeo4jGraphProviderCreateNodes:
    """Test create_nodes method."""

    @pytest.mark.asyncio
    async def test_create_nodes_empty_list(self) -> None:
        """Returns 0 when given empty node list."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )
        result = await provider.create_nodes([], "Person")
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_nodes_single_node(self) -> None:
        """Creates single node correctly."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        # Mock the session and result
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=1)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        nodes = [{"id": "1", "name": "Alice", "role": "Engineer"}]
        result = await provider.create_nodes(nodes, "Person")

        assert result == 1
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "MERGE (n:Person" in call_args[0][0]
        assert call_args[1]["nodes"] == nodes

    @pytest.mark.asyncio
    async def test_create_nodes_batch_processing(self) -> None:
        """Processes nodes in batches."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
            batch_size=2,
        )

        # Mock the session and result
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=2)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        nodes = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
            {"id": "3", "name": "Charlie"},
            {"id": "4", "name": "Diana"},
            {"id": "5", "name": "Eve"},
        ]
        result = await provider.create_nodes(nodes, "Person")

        # 5 nodes with batch_size=2 should result in 3 batches
        # (2 + 2 + 1), but mock returns 2 each time
        assert result == 6  # 3 batches * 2 returned per batch
        assert mock_session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_create_nodes_with_merge_keys(self) -> None:
        """Uses merge keys correctly in query."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=1)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        nodes = [{"id": "1", "email": "alice@example.com", "name": "Alice"}]
        await provider.create_nodes(
            nodes, "Person", merge_on="id", merge_keys=["email"]
        )

        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "id: node.id" in query
        assert "email: node.email" in query


class TestNeo4jGraphProviderCreateRelationships:
    """Test create_relationships method."""

    @pytest.mark.asyncio
    async def test_create_relationships_empty_list(self) -> None:
        """Returns 0 when given empty relationship list."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )
        result = await provider.create_relationships(
            [], "WORKS_AT", "Person", "Organization"
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_relationships_single_rel(self) -> None:
        """Creates single relationship correctly."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=1)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        rels = [{"from_id": "1", "to_id": "2"}]
        result = await provider.create_relationships(
            rels, "WORKS_AT", "Person", "Organization"
        )

        assert result == 1
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "MERGE (a)-[r:WORKS_AT" in query
        assert "MATCH (a:Person" in query
        assert "MATCH (b:Organization" in query

    @pytest.mark.asyncio
    async def test_create_relationships_with_properties(self) -> None:
        """Creates relationships with properties correctly."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(return_value=1)

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        rels = [{"from_id": "1", "to_id": "2", "since": "2020-01-01"}]
        await provider.create_relationships(rels, "WORKS_AT", "Person", "Organization")

        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "since: rel.since" in query


class TestNeo4jGraphProviderLifecycle:
    """Test provider lifecycle methods."""

    @pytest.mark.asyncio
    async def test_close_closes_driver(self) -> None:
        """Close method closes the driver."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_driver = AsyncMock()
        mock_driver.close = AsyncMock()

        provider._driver = mock_driver

        await provider.close()

        mock_driver.close.assert_called_once()
        assert provider._driver is None

    @pytest.mark.asyncio
    async def test_close_when_no_driver(self) -> None:
        """Close does nothing when driver is None."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        # Should not raise
        await provider.close()
        assert provider._driver is None

    @pytest.mark.asyncio
    async def test_verify_connectivity(self) -> None:
        """Verify connectivity calls driver method."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()

        with patch.object(provider, "_get_driver", return_value=mock_driver):
            await provider.verify_connectivity()
            mock_driver.verify_connectivity.assert_called_once()


class TestNeo4jGraphProviderSession:
    """Test session context manager."""

    @pytest.mark.asyncio
    async def test_session_returns_context_manager(self) -> None:
        """Session method returns async context manager."""
        provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        provider._driver = mock_driver

        async with provider.session() as session:
            assert session is mock_session
