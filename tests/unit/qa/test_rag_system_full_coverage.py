"""Additional tests to achieve 100% coverage for src/qa/rag_system.py."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, patch

from src.qa.rag_system import QAKnowledgeGraph


class FakeDoc:
    """Fake document for vector search results."""

    def __init__(self, content: str) -> None:
        self.page_content = content


class FakeVectorStore:
    """Fake vector store for testing."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents

    def similarity_search(self, query: str, k: int = 5) -> list[FakeDoc]:
        """Return fake documents."""
        return [FakeDoc(c) for c in self._contents[:k]]


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


@patch("src.qa.rag_system.initialize_connection")
@patch("src.qa.rag_system.ensure_formatting_rule_schema")
@patch("src.qa.rag_system.get_graph_provider")
@patch("src.qa.rag_system.init_vector_store")
@patch.dict("os.environ", {"GEMINI_API_KEY": "AIza" + "A" * 35}, clear=False)
def test_find_relevant_rules_with_vector_store(
    mock_init_vs: Mock,
    mock_get_provider: Mock,
    mock_ensure_schema: Mock,
    mock_init_conn: Mock,
) -> None:
    """Test find_relevant_rules when vector store is available (lines 204-205).

    This test ensures that when a vector store is initialized, the method
    properly calls similarity_search and returns page_content from results.
    """
    # Setup mocks
    mock_driver = FakeDriver()
    mock_init_conn.return_value = (mock_driver, None)
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    # Create a fake vector store with test data
    fake_vs = FakeVectorStore(["rule1", "rule2", "rule3"])
    mock_init_vs.return_value = fake_vs

    # Create QAKnowledgeGraph instance (this will initialize vector store)
    kg = QAKnowledgeGraph()

    # Call find_relevant_rules - this should execute lines 204-205
    results = kg.find_relevant_rules("test query", k=2)

    # Verify the results
    assert results == ["rule1", "rule2"]
    assert len(results) == 2


@patch("src.qa.rag_system.initialize_connection")
@patch("src.qa.rag_system.ensure_formatting_rule_schema")
@patch("src.qa.rag_system.get_graph_provider")
def test_get_formatting_rules_transform_function(
    mock_get_provider: Mock,
    mock_ensure_schema: Mock,
    mock_init_conn: Mock,
) -> None:
    """Test get_formatting_rules transform function execution (lines 346-347).

    This test ensures that the transform_to_formatted function inside
    get_formatting_rules is properly executed when records are returned.
    """
    # Setup mocks
    mock_driver = FakeDriver()
    mock_init_conn.return_value = (mock_driver, None)
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    # Create QAKnowledgeGraph instance
    kg = QAKnowledgeGraph()

    # Mock the query executor to return test records
    mock_records = [
        {"category": "test_category", "text": "test rule 1"},
        {"category": "test_category", "text": "test rule 2"},
    ]

    with patch.object(
        kg.query_executor,
        "execute_with_fallback",
    ) as mock_execute:
        # Configure mock to call the transform function
        def side_effect(
            query: str, params: dict[str, Any], default: Any, transform: Any = None
        ) -> Any:
            if transform:
                # This will execute lines 346-347 inside transform_to_formatted
                return transform(mock_records)
            return default

        mock_execute.side_effect = side_effect

        # Call get_formatting_rules - this should execute the transform function
        result = kg.get_formatting_rules("eval")

        # Verify that the transform was called and returned formatted rules
        assert isinstance(result, str)
        mock_execute.assert_called_once()


@patch("src.qa.rag_system.initialize_connection")
@patch("src.qa.rag_system.ensure_formatting_rule_schema")
@patch("src.qa.rag_system.get_graph_provider")
@patch("src.qa.rag_system.create_graph_session")
def test_graph_session_context_manager(
    mock_create_session: Mock,
    mock_get_provider: Mock,
    mock_ensure_schema: Mock,
    mock_init_conn: Mock,
) -> None:
    """Test graph_session context manager execution (lines 383-385).

    This test ensures that the graph_session context manager properly
    delegates to create_graph_session with the correct parameters.
    """
    # Setup mocks
    mock_driver = FakeDriver()
    mock_init_conn.return_value = (mock_driver, None)
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    # Mock the session that create_graph_session will yield
    mock_session = MagicMock()
    mock_create_session.return_value = iter([mock_session])

    # Create QAKnowledgeGraph instance
    kg = QAKnowledgeGraph()

    # Use the graph_session context manager - this should execute lines 383-385
    with kg.graph_session() as session:
        # Verify we got a session
        assert session is not None

    # Verify that create_graph_session was called with correct parameters
    mock_create_session.assert_called_once_with(kg._graph, kg._graph_provider)
