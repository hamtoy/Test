# tests/test_neo4j_optimizer.py
"""Tests for Neo4j 2-Tier Index Manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.cli import parse_args, run_neo4j_optimization
from src.infra.neo4j_optimizer import TwoTierIndexManager, OptimizedQueries


class TestTwoTierIndexManagerInit:
    """Test TwoTierIndexManager initialization."""

    def test_init_stores_driver(self) -> None:
        """Manager stores the driver reference."""
        mock_driver = MagicMock()
        manager = TwoTierIndexManager(mock_driver)
        assert manager.driver is mock_driver


class TestTwoTierIndexManagerExtractName:
    """Test index name extraction helper."""

    def test_extract_index_name_regular(self) -> None:
        """Extracts name from regular CREATE INDEX statement."""
        query = "CREATE INDEX rule_id_idx IF NOT EXISTS FOR (r:Rule) ON (r.id)"
        name = TwoTierIndexManager._extract_index_name(query)
        assert name == "rule_id_idx"

    def test_extract_index_name_vector(self) -> None:
        """Extracts name from CREATE VECTOR INDEX statement."""
        query = "CREATE VECTOR INDEX chunk_embedding_idx IF NOT EXISTS FOR (c:Chunk) ON (c.embedding)"
        name = TwoTierIndexManager._extract_index_name(query)
        assert name == "chunk_embedding_idx"

    def test_extract_index_name_multiline(self) -> None:
        """Extracts name from multiline query."""
        query = """
            CREATE INDEX document_id_idx IF NOT EXISTS
            FOR (d:Document) ON (d.id)
        """
        name = TwoTierIndexManager._extract_index_name(query)
        assert name == "document_id_idx"

    def test_extract_index_name_invalid(self) -> None:
        """Returns unknown for invalid queries."""
        query = "SHOW INDEXES"
        name = TwoTierIndexManager._extract_index_name(query)
        assert name == "unknown"


class TestTwoTierIndexManagerObjectIndexes:
    """Test Tier 1 object index creation."""

    @pytest.mark.asyncio
    async def test_create_object_indexes(self) -> None:
        """Creates object indexes for all node types."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        await manager.create_object_indexes()

        # Check that session.run was called for each index
        # 8 object indexes should be created
        assert mock_session.run.call_count == 8

        # Check that key indexes are created
        call_queries = [call[0][0] for call in mock_session.run.call_args_list]
        assert any("rule_id_idx" in q for q in call_queries)
        assert any("document_id_idx" in q for q in call_queries)
        assert any("chunk_id_idx" in q for q in call_queries)
        assert any("chunk_embedding_idx" in q for q in call_queries)


class TestTwoTierIndexManagerTriadIndexes:
    """Test Tier 2 triad index creation."""

    @pytest.mark.asyncio
    async def test_create_triad_indexes(self) -> None:
        """Creates triad indexes for relationship patterns."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        await manager.create_triad_indexes()

        # 4 triad indexes should be created
        assert mock_session.run.call_count == 4

        call_queries = [call[0][0] for call in mock_session.run.call_args_list]
        assert any("triad_document_rule_idx" in q for q in call_queries)
        assert any("triad_extracted_from_idx" in q for q in call_queries)
        assert any("triad_has_chunk_idx" in q for q in call_queries)
        assert any("triad_relates_to_idx" in q for q in call_queries)


class TestTwoTierIndexManagerCreateAll:
    """Test combined index creation."""

    @pytest.mark.asyncio
    async def test_create_all_indexes(self) -> None:
        """Creates both tiers of indexes."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        await manager.create_all_indexes()

        # 8 object indexes + 4 triad indexes = 12 total
        assert mock_session.run.call_count == 12


class TestTwoTierIndexManagerListIndexes:
    """Test index listing."""

    @pytest.mark.asyncio
    async def test_list_all_indexes(self) -> None:
        """Lists all indexes from the database."""
        mock_indexes = [
            {"name": "rule_id_idx", "type": "RANGE"},
            {"name": "document_id_idx", "type": "RANGE"},
        ]

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=mock_indexes)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        indexes = await manager.list_all_indexes()

        assert len(indexes) == 2
        assert indexes[0]["name"] == "rule_id_idx"
        assert indexes[1]["name"] == "document_id_idx"


class TestTwoTierIndexManagerDropIndexes:
    """Test index dropping."""

    @pytest.mark.asyncio
    async def test_drop_all_indexes(self) -> None:
        """Drops all non-system indexes."""
        mock_indexes = [
            {"name": "rule_id_idx", "type": "RANGE"},
            {"name": "system_lookup", "type": "LOOKUP"},  # Should be skipped
            {"name": "document_id_idx", "type": "RANGE"},
        ]

        mock_list_result = AsyncMock()
        mock_list_result.data = AsyncMock(return_value=mock_indexes)

        mock_drop_result = AsyncMock()
        mock_drop_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        # First call is SHOW INDEXES, subsequent calls are DROP
        mock_session.run = AsyncMock(
            side_effect=[mock_list_result, mock_drop_result, mock_drop_result]
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        await manager.drop_all_indexes()

        # Should call run 3 times: 1 for list + 2 for drops (skips LOOKUP)
        assert mock_session.run.call_count == 3

        # Verify drop queries
        drop_calls = [call[0][0] for call in mock_session.run.call_args_list[1:]]
        assert "DROP INDEX rule_id_idx IF EXISTS" in drop_calls
        assert "DROP INDEX document_id_idx IF EXISTS" in drop_calls


class TestTwoTierIndexManagerAnalyzeUsage:
    """Test index usage analysis."""

    @pytest.mark.asyncio
    async def test_analyze_index_usage(self) -> None:
        """Analyzes index usage statistics."""
        mock_data = {"indexHits": 1000, "indexMisses": 50}

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"data": mock_data}])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        usage = await manager.analyze_index_usage()

        assert usage == mock_data

    @pytest.mark.asyncio
    async def test_analyze_index_usage_empty(self) -> None:
        """Returns empty dict when no stats available."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        manager = TwoTierIndexManager(mock_driver)
        usage = await manager.analyze_index_usage()

        assert usage == {}


class TestOptimizedQueries:
    """Test optimized query generation."""

    def test_find_rules_by_document(self) -> None:
        """Generates correct query for finding rules by document."""
        query = OptimizedQueries.find_rules_by_document()
        assert "$document_id" in query
        assert ":Document" in query
        assert ":DOCUMENT_RULE" in query
        assert ":Rule" in query

    def test_find_related_rules(self) -> None:
        """Generates correct query for finding related rules."""
        query = OptimizedQueries.find_related_rules(max_depth=3)
        assert "$rule_id" in query
        assert ":RELATES_TO*1..3" in query
        assert "ORDER BY distance" in query

    def test_find_related_rules_default_depth(self) -> None:
        """Uses default depth of 2."""
        query = OptimizedQueries.find_related_rules()
        assert ":RELATES_TO*1..2" in query

    def test_semantic_search_with_graph(self) -> None:
        """Generates correct hybrid search query."""
        query = OptimizedQueries.semantic_search_with_graph(k=5)
        assert "$k" in query
        assert "$embedding" in query
        assert "chunk_embedding_idx" in query
        assert ":HAS_CHUNK" in query
        assert ":DOCUMENT_RULE" in query
        assert "ORDER BY score DESC" in query


class TestCLIOptimizeNeo4j:
    """Test CLI Neo4j optimization function."""

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_missing_env(self) -> None:
        """Raises error when environment variables are missing."""
        with pytest.raises(EnvironmentError) as exc_info:
            await run_neo4j_optimization()

        assert "NEO4J_URI" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_success(self, monkeypatch) -> None:
        """Successfully runs optimization with valid env."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_driver.close = AsyncMock()

        with patch("neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
            await run_neo4j_optimization(drop_existing=False)

        # Verify driver was closed
        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_with_drop(self, monkeypatch) -> None:
        """Drops existing indexes when flag is set."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        # Mock for list_all_indexes (returns empty, so no drops needed)
        mock_list_result = AsyncMock()
        mock_list_result.data = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_list_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_driver = AsyncMock()
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_driver.close = AsyncMock()

        with patch("neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
            await run_neo4j_optimization(drop_existing=True)

        # Should have called session.run for:
        # - SHOW INDEXES (for drop)
        # - 12 index creation queries
        # - SHOW INDEXES (for listing after)
        assert mock_session.run.call_count >= 13


class TestCLIArgsOptimizeNeo4j:
    """Test CLI argument parsing for Neo4j optimization."""

    def test_parse_args_optimize_neo4j(self) -> None:
        """Parses --optimize-neo4j flag."""
        args = parse_args(["--optimize-neo4j"])
        assert args.optimize_neo4j is True
        assert args.drop_existing_indexes is False

    def test_parse_args_drop_existing(self) -> None:
        """Parses --drop-existing-indexes flag."""
        args = parse_args(["--optimize-neo4j", "--drop-existing-indexes"])
        assert args.optimize_neo4j is True
        assert args.drop_existing_indexes is True
