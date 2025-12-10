"""Comprehensive test coverage for src/qa/rag_system.py."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.qa.rag_system import QAKnowledgeGraph


class FakeSession:
    """Fake Neo4j session for testing."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.rows = rows or []

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    def run(self, cypher: str, **params: Any) -> list[Any]:
        return self.rows


class FakeDriver:
    """Fake Neo4j driver for testing."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self._session = FakeSession(rows)

    def session(self) -> FakeSession:
        return self._session

    def close(self) -> None:
        pass


def _make_kg_minimal() -> QAKnowledgeGraph:
    """Create minimal KG instance bypassing __init__."""
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = FakeDriver()  # type: ignore[assignment]
    kg._graph_provider = None
    kg._graph_finalizer = None
    kg._vector_store = None
    kg._closed = False  # Initialize closed flag
    kg.neo4j_uri = "bolt://localhost:7687"
    kg.neo4j_user = "neo4j"
    kg.neo4j_password = "password"
    return kg


class TestQAKnowledgeGraphInit:
    """Test QAKnowledgeGraph initialization."""

    @patch("src.qa.rag_system.initialize_connection")
    @patch("src.qa.rag_system.ensure_formatting_rule_schema")
    def test_init_with_graph_provider(
        self, mock_ensure_schema: Mock, mock_init_conn: Mock
    ) -> None:
        """Test initialization with custom graph provider."""
        mock_provider = MagicMock()
        mock_driver = FakeDriver()
        mock_init_conn.return_value = (mock_driver, None)

        kg = QAKnowledgeGraph(graph_provider=mock_provider)

        assert kg._graph_provider == mock_provider
        mock_init_conn.assert_called_once()
        mock_ensure_schema.assert_called_once()

    @patch("src.qa.rag_system.initialize_connection")
    @patch("src.qa.rag_system.ensure_formatting_rule_schema")
    @patch("src.qa.rag_system.get_graph_provider")
    def test_init_without_graph_provider(
        self,
        mock_get_provider: Mock,
        mock_ensure_schema: Mock,
        mock_init_conn: Mock,
    ) -> None:
        """Test initialization without graph provider uses factory."""
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        mock_driver = FakeDriver()
        mock_init_conn.return_value = (mock_driver, None)

        kg = QAKnowledgeGraph()

        mock_get_provider.assert_called_once()
        assert kg._graph_provider == mock_provider

    @patch("src.qa.rag_system.initialize_connection")
    @patch("src.qa.rag_system.ensure_formatting_rule_schema")
    @patch("src.qa.rag_system.get_graph_provider")
    @patch.dict(
        os.environ,
        {
            "NEO4J_URI": "bolt://custom:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "password",
        },
        clear=False,
    )
    def test_init_with_env_credentials(
        self, mock_get_provider: Mock, mock_ensure_schema: Mock, mock_init_conn: Mock
    ) -> None:
        """Test initialization picks up environment variables."""
        mock_driver = FakeDriver()
        mock_init_conn.return_value = (mock_driver, None)
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        kg = QAKnowledgeGraph()

        assert kg.neo4j_uri == "bolt://custom:7687"


class TestVectorStoreInitialization:
    """Test vector store initialization logic."""

    @patch("src.qa.rag_system.initialize_connection")
    @patch("src.qa.rag_system.ensure_formatting_rule_schema")
    @patch("src.qa.rag_system.init_vector_store")
    @patch("src.qa.rag_system.get_graph_provider")
    @patch.dict(os.environ, {"GEMINI_API_KEY": "AIza" + "A" * 35}, clear=False)
    def test_init_vector_store_with_api_key(
        self,
        mock_get_provider: Mock,
        mock_init_vs: Mock,
        mock_ensure_schema: Mock,
        mock_init_conn: Mock,
    ) -> None:
        """Test vector store is initialized when GEMINI_API_KEY is set."""
        mock_driver = FakeDriver()
        mock_init_conn.return_value = (mock_driver, None)
        mock_vector_store = MagicMock()
        mock_init_vs.return_value = mock_vector_store
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        kg = QAKnowledgeGraph()

        mock_init_vs.assert_called_once()
        assert kg._vector_store == mock_vector_store

    @patch("src.qa.rag_system.initialize_connection")
    @patch("src.qa.rag_system.ensure_formatting_rule_schema")
    @patch("src.qa.rag_system.init_vector_store")
    @patch("src.qa.rag_system.get_graph_provider")
    @patch("src.qa.rag_system.AppConfig")
    def test_init_vector_store_without_api_key(
        self,
        mock_app_config: Mock,
        mock_get_provider: Mock,
        mock_init_vs: Mock,
        mock_ensure_schema: Mock,
        mock_init_conn: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test vector store is skipped when GEMINI_API_KEY is not set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        mock_driver = FakeDriver()
        mock_init_conn.return_value = (mock_driver, None)
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider

        # Bypass AppConfig validation by mocking it
        mock_config = MagicMock()
        mock_app_config.return_value = mock_config

        kg = QAKnowledgeGraph()

        mock_init_vs.assert_not_called()
        # _vector_store should remain None since no key was provided
        assert kg._vector_store is None


class TestPropertyAccessors:
    """Test lazy property accessors."""

    @patch("src.qa.rag_system.CacheMetrics")
    def test_cache_metrics_lazy_init(self, mock_cache_metrics: Mock) -> None:
        """Test cache_metrics property lazy initialization."""
        kg = _make_kg_minimal()
        # Delete to simulate bypassed __init__
        if hasattr(kg, "_cache_metrics"):
            delattr(kg, "_cache_metrics")

        mock_metrics = MagicMock()
        mock_cache_metrics.return_value = mock_metrics

        metrics = kg.cache_metrics

        assert metrics is not None
        mock_cache_metrics.assert_called_once_with(namespace="qa_kg")

    @patch("src.qa.rag_system.QueryExecutor")
    def test_query_executor_lazy_init(self, mock_query_executor: Mock) -> None:
        """Test query_executor property lazy initialization."""
        kg = _make_kg_minimal()
        # Delete to simulate bypassed __init__
        if hasattr(kg, "_query_executor"):
            delattr(kg, "_query_executor")

        mock_executor = MagicMock()
        mock_query_executor.return_value = mock_executor

        executor = kg.query_executor

        assert executor is not None
        mock_query_executor.assert_called_once()


class TestSessionValidation:
    """Test session validation."""

    @patch("src.qa.rag_system.validate_session_structure")
    def test_validate_session(self, mock_validate: Mock) -> None:
        """Test validate_session delegates to validator."""
        kg = _make_kg_minimal()
        session_data = {"turns": [{"query": "test", "answer": "response"}]}
        expected_result = {"valid": True}
        mock_validate.return_value = expected_result

        result = kg.validate_session(session_data)

        mock_validate.assert_called_once_with(session_data)
        assert result == expected_result


class TestFormattingRules:
    """Test formatting rules retrieval."""

    def test_get_formatting_rules_for_query_type(self) -> None:
        """Test get_formatting_rules_for_query_type."""
        fake_rules = [{"id": "rule1", "text": "Rule 1"}]
        kg = _make_kg_minimal()
        kg._graph = FakeDriver(fake_rules)  # type: ignore[assignment]
        kg._query_executor = MagicMock()
        kg._query_executor.execute_with_fallback.return_value = fake_rules

        result = kg.get_formatting_rules_for_query_type("explanation")

        assert result == fake_rules
        kg._query_executor.execute_with_fallback.assert_called_once()

    @patch("src.qa.rag_system.format_rules")
    def test_get_formatting_rules_with_transform(self, mock_format: Mock) -> None:
        """Test get_formatting_rules applies transform function."""
        kg = _make_kg_minimal()
        kg._query_executor = MagicMock()
        formatted_str = "# Test\n- Test rule"

        # Mock the transform being applied
        kg._query_executor.execute_with_fallback.return_value = formatted_str
        mock_format.return_value = formatted_str

        result = kg.get_formatting_rules("eval")

        assert isinstance(result, str)
        assert result == formatted_str


class TestRuleManagement:
    """Test rule CRUD operations."""

    def test_update_rule(self) -> None:
        """Test update_rule delegates to RuleManager."""
        kg = _make_kg_minimal()
        kg._rule_manager = MagicMock()

        kg.update_rule("rule_123", "Updated text")

        kg._rule_manager.update_rule.assert_called_once_with("rule_123", "Updated text")

    def test_add_rule(self) -> None:
        """Test add_rule delegates to RuleManager."""
        kg = _make_kg_minimal()
        kg._rule_manager = MagicMock()
        kg._rule_manager.add_rule.return_value = "new_rule_id"

        result = kg.add_rule("explanation", "New rule text")

        assert result == "new_rule_id"
        kg._rule_manager.add_rule.assert_called_once_with(
            "explanation", "New rule text"
        )

    def test_delete_rule(self) -> None:
        """Test delete_rule delegates to RuleManager."""
        kg = _make_kg_minimal()
        kg._rule_manager = MagicMock()

        kg.delete_rule("rule_456")

        kg._rule_manager.delete_rule.assert_called_once_with("rule_456")


class TestResourceCleanup:
    """Test resource cleanup and destructor."""

    @patch("src.qa.rag_system.close_connections")
    def test_close(self, mock_close: Mock) -> None:
        """Test close method cleans up resources."""
        kg = _make_kg_minimal()
        kg._graph_finalizer = MagicMock()
        original_graph = kg._graph  # Capture the specific graph instance

        kg.close()

        # Verify close() was called with OUR instance's graph
        # (other tests may trigger GC of their KG instances)
        call_args_list = [call.args for call in mock_close.call_args_list]
        our_call_found = any(args[0] is original_graph for args in call_args_list)
        assert our_call_found, (
            "close_connections was not called with our graph instance"
        )
        assert kg._graph is None
        assert kg._graph_finalizer is None

    @patch("src.qa.rag_system.close_connections")
    def test_destructor_calls_close(self, mock_close: Mock) -> None:
        """Test __del__ attempts to close connections."""
        kg = _make_kg_minimal()
        kg._graph_finalizer = MagicMock()
        original_graph = kg._graph  # Capture the specific graph instance

        kg.__del__()

        # Verify __del__() was called with OUR instance's graph
        call_args_list = [call.args for call in mock_close.call_args_list]
        our_call_found = any(args[0] is original_graph for args in call_args_list)
        assert our_call_found, (
            "close_connections was not called with our graph instance"
        )


class TestBatchOperations:
    """Test batch operations."""

    def test_get_rules_by_batch_id(self) -> None:
        """Test get_rules_by_batch_id delegates correctly."""
        kg = _make_kg_minimal()
        kg._rule_upsert_manager = MagicMock()
        expected_rules = [{"id": "rule1", "batch_id": "batch_123"}]
        kg._rule_upsert_manager.get_rules_by_batch_id.return_value = expected_rules

        result = kg.get_rules_by_batch_id("batch_123")

        assert result == expected_rules
        kg._rule_upsert_manager.get_rules_by_batch_id.assert_called_once_with(
            "batch_123"
        )

    def test_rollback_batch(self) -> None:
        """Test rollback_batch delegates correctly."""
        kg = _make_kg_minimal()
        kg._rule_upsert_manager = MagicMock()
        expected_result = {"deleted": 5}
        kg._rule_upsert_manager.rollback_batch.return_value = expected_result

        result = kg.rollback_batch("batch_456")

        assert result == expected_result
        kg._rule_upsert_manager.rollback_batch.assert_called_once_with("batch_456")


class TestQueryMethods:
    """Test various query methods."""

    def test_get_rules_for_query_type(self) -> None:
        """Test get_rules_for_query_type returns rules."""
        kg = _make_kg_minimal()
        kg._query_executor = MagicMock()
        expected_rules = [{"id": "rule1", "text": "Rule text"}]
        kg._query_executor.execute_with_fallback.return_value = expected_rules

        result = kg.get_rules_for_query_type("explanation")

        assert result == expected_rules

    def test_get_best_practices(self) -> None:
        """Test get_best_practices returns practices."""
        kg = _make_kg_minimal()
        kg._query_executor = MagicMock()
        expected_practices = [{"id": "bp1", "text": "Best practice"}]
        kg._query_executor.execute_with_fallback.return_value = expected_practices

        result = kg.get_best_practices("explanation")

        assert result == expected_practices

    def test_get_examples(self) -> None:
        """Test get_examples returns examples."""
        kg = _make_kg_minimal()
        kg._query_executor = MagicMock()
        expected_examples = [{"id": "ex1", "text": "Example text"}]
        kg._query_executor.execute_with_fallback.return_value = expected_examples

        result = kg.get_examples(limit=10)

        assert result == expected_examples
