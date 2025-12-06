"""Comprehensive tests for src/qa/rag_system.py to improve coverage to 80%+."""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.config import AppConfig
from src.qa.rag_system import QAKnowledgeGraph


@pytest.fixture
def mock_graph_driver():
    """Mock Neo4j driver for testing."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    driver.close = MagicMock()
    return driver


@pytest.fixture
def mock_graph_provider():
    """Mock GraphProvider for testing."""
    provider = AsyncMock()
    session = AsyncMock()
    provider.session.return_value.__aenter__.return_value = session
    provider.session.return_value.__aexit__.return_value = None
    provider.close = AsyncMock()
    return provider


@pytest.fixture
def mock_vector_store():
    """Mock vector store for testing."""
    store = MagicMock()
    doc1 = MagicMock()
    doc1.page_content = "Rule 1: Test rule content"
    doc2 = MagicMock()
    doc2.page_content = "Rule 2: Another test rule"
    store.similarity_search.return_value = [doc1, doc2]
    return store


class TestQAKnowledgeGraphInit:
    """Test QAKnowledgeGraph initialization."""

    def test_init_with_provider(self, mock_graph_provider):
        """Test initialization with graph provider."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="password",
                graph_provider=mock_graph_provider,
            )

            assert kg._graph_provider == mock_graph_provider
            assert kg.neo4j_uri == "bolt://localhost:7687"

    def test_init_without_provider_creates_driver(self, monkeypatch):
        """Test initialization without provider creates driver."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")
        monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "0" * 35)

        mock_driver = MagicMock()
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_driver):
            kg = QAKnowledgeGraph()

            assert kg._graph is not None
            assert kg.neo4j_uri == "bolt://localhost:7687"

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization using environment variables."""
        monkeypatch.setenv("NEO4J_URI", "bolt://test:7687")
        monkeypatch.setenv("NEO4J_USER", "testuser")
        monkeypatch.setenv("NEO4J_PASSWORD", "testpass")

        mock_driver = MagicMock()
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                kg = QAKnowledgeGraph()

                assert kg.neo4j_uri == "bolt://test:7687"
                assert kg.neo4j_user == "testuser"
                assert kg.neo4j_password == "testpass"

    def test_init_requires_credentials_without_provider(self, monkeypatch):
        """Test that initialization requires credentials when no provider."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        with patch("src.qa.rag_system.get_graph_provider", return_value=None):
            with pytest.raises((ValueError, RuntimeError)):
                QAKnowledgeGraph()


class TestCacheMetrics:
    """Test cache metrics property."""

    def test_cache_metrics_lazy_initialization(self, mock_graph_provider):
        """Test that cache_metrics is lazily initialized."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

            # Access cache_metrics multiple times
            metrics1 = kg.cache_metrics
            metrics2 = kg.cache_metrics

            assert metrics1 is not None
            assert metrics1 is metrics2  # Same instance

    def test_cache_metrics_creates_if_missing(self, mock_graph_provider):
        """Test that cache_metrics creates instance if missing."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)
            # Simulate missing cache_metrics
            kg._cache_metrics = None

            metrics = kg.cache_metrics

            assert metrics is not None
            assert metrics._namespace == "qa_kg"


class TestVectorStore:
    """Test vector store initialization and usage."""

    def test_init_vector_store_without_api_key(self, monkeypatch, mock_graph_provider):
        """Test vector store skips initialization without API key."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

            assert kg._vector_store is None

    def test_init_vector_store_with_api_key(self, monkeypatch, mock_graph_provider, mock_vector_store):
        """Test vector store initialization with API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "0" * 35)

        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            with patch("src.qa.rag_system.init_vector_store", return_value=mock_vector_store):
                kg = QAKnowledgeGraph(
                    neo4j_uri="bolt://localhost:7687",
                    neo4j_user="neo4j",
                    neo4j_password="password",
                    graph_provider=mock_graph_provider,
                )

                assert kg._vector_store == mock_vector_store

    def test_find_relevant_rules_without_vector_store(self, mock_graph_provider):
        """Test find_relevant_rules returns empty when no vector store."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)
            kg._vector_store = None

            rules = kg.find_relevant_rules("test query", k=5)

            assert rules == []

    def test_find_relevant_rules_with_vector_store(self, mock_graph_provider, mock_vector_store):
        """Test find_relevant_rules returns results from vector store."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)
            kg._vector_store = mock_vector_store

            rules = kg.find_relevant_rules("test query", k=3)

            assert len(rules) == 2
            assert "Rule 1" in rules[0]
            assert "Rule 2" in rules[1]
            mock_vector_store.similarity_search.assert_called_once_with("test query", k=3)


class TestGetConstraintsForQueryType:
    """Test get_constraints_for_query_type method."""

    def test_get_constraints_sync_driver(self, mock_graph_driver):
        """Test getting constraints using sync driver."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value

                # Mock query results
                mock_record1 = {"id": "c1", "type": "length", "description": "Test constraint 1"}
                mock_record2 = {"id": "c2", "type": "format", "description": "Test constraint 2"}
                session.run.return_value = [mock_record1, mock_record2]

                constraints = kg.get_constraints_for_query_type("explanation")

                assert len(constraints) == 2
                assert constraints[0]["id"] == "c1"
                assert constraints[1]["id"] == "c2"
                monkeypatch.undo()

    def test_get_constraints_async_provider(self, mock_graph_provider):
        """Test getting constraints using async provider."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)
            kg._graph = None  # Force async path

            session = mock_graph_provider.session.return_value.__aenter__.return_value

            # Mock async iteration
            mock_record1 = {"id": "c1", "type": "length"}
            mock_record2 = {"id": "c2", "type": "format"}

            async def async_iter():
                for record in [mock_record1, mock_record2]:
                    yield record

            mock_result = AsyncMock()
            mock_result.__aiter__ = lambda self: async_iter()
            session.run.return_value = mock_result

            constraints = kg.get_constraints_for_query_type("explanation")

            assert len(constraints) == 2
            assert constraints[0]["id"] == "c1"

    def test_get_constraints_returns_empty_no_provider(self):
        """Test getting constraints returns empty when no provider available."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=None):
            with patch("src.qa.rag_system.create_sync_driver", side_effect=Exception("No driver")):
                kg = QAKnowledgeGraph.__new__(QAKnowledgeGraph)
                kg._graph = None
                kg._graph_provider = None

                constraints = kg.get_constraints_for_query_type("explanation")

                assert constraints == []


class TestGetRulesForQueryType:
    """Test get_rules_for_query_type method."""

    def test_get_rules_sync_driver(self, mock_graph_driver):
        """Test getting rules using sync driver."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value

                mock_record = {
                    "id": "r1",
                    "name": "Rule 1",
                    "text": "Test rule",
                    "category": "formatting",
                    "priority": "high",
                    "source": "manual",
                }
                session.run.return_value = [mock_record]

                rules = kg.get_rules_for_query_type("explanation")

                assert len(rules) == 1
                assert rules[0]["id"] == "r1"
                assert rules[0]["text"] == "Test rule"
                monkeypatch.undo()

    def test_get_rules_handles_sync_error(self, mock_graph_driver):
        """Test get_rules handles sync driver errors gracefully."""
        from neo4j.exceptions import Neo4jError

        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value
                session.run.side_effect = Neo4jError("Connection error")

                # Should fall back to async provider (if available) or return []
                kg._graph_provider = None
                rules = kg.get_rules_for_query_type("explanation")

                assert rules == []
                monkeypatch.undo()


class TestGetBestPractices:
    """Test get_best_practices method."""

    def test_get_best_practices_sync(self, mock_graph_driver):
        """Test getting best practices with sync driver."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value

                mock_bp = {"id": "bp1", "text": "Best practice text"}
                session.run.return_value = [mock_bp]

                best_practices = kg.get_best_practices("explanation")

                assert len(best_practices) == 1
                assert best_practices[0]["id"] == "bp1"
                monkeypatch.undo()

    def test_get_best_practices_requires_driver(self):
        """Test get_best_practices raises when no driver available."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=None):
            kg = QAKnowledgeGraph.__new__(QAKnowledgeGraph)
            kg._graph = None
            kg._graph_provider = None

            with pytest.raises(ValueError, match="Graph driver must be initialized"):
                kg.get_best_practices("explanation")


class TestGetExamples:
    """Test get_examples method."""

    def test_get_examples_with_limit(self, mock_graph_driver):
        """Test getting examples with custom limit."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value

                examples = [
                    {"id": "ex1", "text": "Example 1", "type": "good"},
                    {"id": "ex2", "text": "Example 2", "type": "bad"},
                ]
                session.run.return_value = examples

                result = kg.get_examples(limit=10)

                assert len(result) == 2
                session.run.assert_called_once()
                # Check that limit parameter was passed
                call_kwargs = session.run.call_args[1]
                assert call_kwargs["limit"] == 10
                monkeypatch.undo()


class TestValidateSession:
    """Test validate_session method."""

    def test_validate_session_structure(self, mock_graph_provider):
        """Test session validation delegates to validator."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            with patch("src.qa.rag_system.validate_session_structure") as mock_validate:
                mock_validate.return_value = {"valid": True, "errors": []}

                kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

                session_data = {
                    "session_id": "test_session",
                    "turns": [{"query": "test", "answer": "response"}],
                }

                result = kg.validate_session(session_data)

                assert result["valid"] is True
                mock_validate.assert_called_once_with(session_data)


class TestFormattingRules:
    """Test formatting rule methods."""

    def test_get_formatting_rules_for_query_type(self, mock_graph_driver):
        """Test getting formatting rules for specific query type."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                session = mock_graph_driver.session.return_value.__enter__.return_value

                mock_rule = {
                    "name": "formatting_rule_1",
                    "description": "Test formatting rule",
                    "priority": 10,
                    "category": "structure",
                    "examples_good": "Good example",
                    "examples_bad": "Bad example",
                }
                session.run.return_value = [mock_rule]

                rules = kg.get_formatting_rules_for_query_type("explanation")

                assert len(rules) == 1
                assert rules[0]["name"] == "formatting_rule_1"
                monkeypatch.undo()

    def test_get_formatting_rules_returns_markdown(self, mock_graph_driver):
        """Test get_formatting_rules returns formatted markdown."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                with patch("src.qa.rag_system.format_rules", return_value="# Formatted Rules"):
                    monkeypatch = pytest.MonkeyPatch()
                    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                    monkeypatch.setenv("NEO4J_USER", "neo4j")
                    monkeypatch.setenv("NEO4J_PASSWORD", "password")

                    kg = QAKnowledgeGraph()
                    session = mock_graph_driver.session.return_value.__enter__.return_value

                    mock_rule = {"text": "Rule text", "priority": 1}
                    session.run.return_value = [mock_rule]

                    result = kg.get_formatting_rules("eval")

                    assert result == "# Formatted Rules"
                    monkeypatch.undo()


class TestRuleMutation:
    """Test rule mutation methods."""

    def test_update_rule(self, mock_graph_driver):
        """Test updating a rule."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                with patch("src.qa.rag_system.clear_global_rule_cache") as mock_clear:
                    monkeypatch = pytest.MonkeyPatch()
                    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                    monkeypatch.setenv("NEO4J_USER", "neo4j")
                    monkeypatch.setenv("NEO4J_PASSWORD", "password")

                    kg = QAKnowledgeGraph()
                    session = mock_graph_driver.session.return_value.__enter__.return_value

                    mock_result = MagicMock()
                    mock_result.single.return_value = {"updated": 1}
                    session.run.return_value = mock_result

                    kg.update_rule("rule_123", "New rule text")

                    session.run.assert_called_once()
                    mock_clear.assert_called_once()
                    monkeypatch.undo()

    def test_add_rule(self, mock_graph_driver):
        """Test adding a new rule."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                with patch("src.qa.rag_system.clear_global_rule_cache") as mock_clear:
                    monkeypatch = pytest.MonkeyPatch()
                    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                    monkeypatch.setenv("NEO4J_USER", "neo4j")
                    monkeypatch.setenv("NEO4J_PASSWORD", "password")

                    kg = QAKnowledgeGraph()
                    session = mock_graph_driver.session.return_value.__enter__.return_value

                    mock_result = MagicMock()
                    mock_result.single.return_value = {"id": "new_rule_id"}
                    session.run.return_value = mock_result

                    rule_id = kg.add_rule("explanation", "New rule text")

                    assert rule_id == "new_rule_id"
                    session.run.assert_called_once()
                    mock_clear.assert_called_once()
                    monkeypatch.undo()

    def test_delete_rule(self, mock_graph_driver):
        """Test deleting a rule."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                with patch("src.qa.rag_system.clear_global_rule_cache") as mock_clear:
                    monkeypatch = pytest.MonkeyPatch()
                    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                    monkeypatch.setenv("NEO4J_USER", "neo4j")
                    monkeypatch.setenv("NEO4J_PASSWORD", "password")

                    kg = QAKnowledgeGraph()
                    session = mock_graph_driver.session.return_value.__enter__.return_value

                    mock_result = MagicMock()
                    mock_summary = MagicMock()
                    mock_summary.counters.nodes_deleted = 1
                    mock_result.consume.return_value = mock_summary
                    session.run.return_value = mock_result

                    kg.delete_rule("rule_123")

                    session.run.assert_called_once()
                    mock_clear.assert_called_once()
                    monkeypatch.undo()


class TestClose:
    """Test close method and cleanup."""

    def test_close_cleans_up_driver(self, mock_graph_driver):
        """Test close method cleans up driver."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()

                kg.close()

                assert kg._graph is None
                mock_graph_driver.close.assert_called_once()
                monkeypatch.undo()

    def test_close_handles_exceptions(self, mock_graph_driver):
        """Test close handles exceptions gracefully."""
        mock_graph_driver.close.side_effect = Exception("Close error")

        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()

                # Should not raise
                kg.close()
                monkeypatch.undo()

    def test_destructor_calls_close(self, mock_graph_driver):
        """Test __del__ calls close."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()
                kg.__del__()

                # Graph should be None after cleanup
                assert kg._graph is None
                monkeypatch.undo()


class TestGraphSession:
    """Test graph_session context manager."""

    def test_graph_session_with_sync_driver(self, mock_graph_driver):
        """Test graph_session uses sync driver when available."""
        with patch("src.qa.rag_system.create_sync_driver", return_value=mock_graph_driver):
            with patch("src.qa.rag_system.get_graph_provider", return_value=None):
                monkeypatch = pytest.MonkeyPatch()
                monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
                monkeypatch.setenv("NEO4J_USER", "neo4j")
                monkeypatch.setenv("NEO4J_PASSWORD", "password")

                kg = QAKnowledgeGraph()

                with kg.graph_session() as session:
                    assert session is not None

                mock_graph_driver.session.assert_called()
                monkeypatch.undo()

    def test_graph_session_yields_none_when_no_graph(self):
        """Test graph_session yields None when no graph available."""
        kg = QAKnowledgeGraph.__new__(QAKnowledgeGraph)
        kg._graph = None
        kg._graph_provider = None

        with kg.graph_session() as session:
            assert session is None


class TestUpsertAutoGeneratedRules:
    """Test upsert_auto_generated_rules method."""

    def test_upsert_auto_generated_rules_delegates(self, mock_graph_provider):
        """Test upsert_auto_generated_rules delegates to RuleUpsertManager."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

            patterns = [
                {
                    "id": "rule_1",
                    "rule": "Test rule",
                    "type_hint": "explanation",
                }
            ]

            with patch.object(kg._rule_upsert_manager, "upsert_auto_generated_rules") as mock_upsert:
                mock_upsert.return_value = {
                    "success": True,
                    "batch_id": "batch_123",
                    "created": {"rules": 1},
                }

                result = kg.upsert_auto_generated_rules(patterns, batch_id="batch_123")

                assert result["success"] is True
                mock_upsert.assert_called_once_with(patterns, "batch_123")


class TestRollbackBatch:
    """Test rollback_batch method."""

    def test_rollback_batch_delegates(self, mock_graph_provider):
        """Test rollback_batch delegates to RuleUpsertManager."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

            with patch.object(kg._rule_upsert_manager, "rollback_batch") as mock_rollback:
                mock_rollback.return_value = {"success": True, "deleted_count": 5}

                result = kg.rollback_batch("batch_123")

                assert result["success"] is True
                assert result["deleted_count"] == 5
                mock_rollback.assert_called_once_with("batch_123")


class TestGetRulesByBatchId:
    """Test get_rules_by_batch_id method."""

    def test_get_rules_by_batch_id_delegates(self, mock_graph_provider):
        """Test get_rules_by_batch_id delegates to RuleUpsertManager."""
        with patch("src.qa.rag_system.get_graph_provider", return_value=mock_graph_provider):
            kg = QAKnowledgeGraph(graph_provider=mock_graph_provider)

            with patch.object(kg._rule_upsert_manager, "get_rules_by_batch_id") as mock_get:
                mock_get.return_value = [
                    {"labels": ["Rule"], "id": "rule_1"},
                    {"labels": ["Rule"], "id": "rule_2"},
                ]

                rules = kg.get_rules_by_batch_id("batch_123")

                assert len(rules) == 2
                mock_get.assert_called_once_with("batch_123")
