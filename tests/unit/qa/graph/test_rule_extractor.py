"""Tests for rule extraction and QA generation module."""

from unittest.mock import MagicMock

import pytest

from src.qa.graph.connection import Neo4jConnectionManager
from src.qa.graph.rule_extractor import RuleExtractor
from src.qa.graph.vector_search import VectorSearchEngine


class TestRuleExtractor:
    """Tests for RuleExtractor class."""

    @pytest.fixture
    def mock_connection(self) -> MagicMock:
        """Create a mock connection manager."""
        connection = MagicMock(spec=Neo4jConnectionManager)
        return connection

    @pytest.fixture
    def mock_vector_engine(self) -> MagicMock:
        """Create a mock vector search engine."""
        engine = MagicMock(spec=VectorSearchEngine)
        return engine

    @pytest.fixture
    def rule_extractor(
        self,
        mock_connection: MagicMock,
        mock_vector_engine: MagicMock,
    ) -> RuleExtractor:
        """Create a RuleExtractor instance with mocks."""
        return RuleExtractor(mock_connection, mock_vector_engine)

    def test_init(
        self,
        mock_connection: MagicMock,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test initialization."""
        extractor = RuleExtractor(mock_connection, mock_vector_engine)

        assert extractor.connection is mock_connection
        assert extractor.vector_engine is mock_vector_engine

    def test_get_rules_for_topic_success(
        self,
        rule_extractor: RuleExtractor,
        mock_connection: MagicMock,
    ) -> None:
        """Test getting rules for a specific topic."""
        expected_results = [
            {
                "rule_id": "r1",
                "rule_content": "Rule 1",
                "constraints": ["C1", "C2"],
                "examples": ["E1"],
            },
            {
                "rule_id": "r2",
                "rule_content": "Rule 2",
                "constraints": ["C3"],
                "examples": [],
            },
        ]
        mock_connection.execute_query.return_value = expected_results

        results = rule_extractor.get_rules_for_topic("machine learning", limit=5)

        assert results == expected_results
        mock_connection.execute_query.assert_called_once()
        call_args = mock_connection.execute_query.call_args
        # Verify that the parameters include topic and limit (passed as second positional arg)
        params = call_args[0][1]  # Second positional argument is the params dict
        assert params["topic"] == "machine learning"
        assert params["limit"] == 5

    def test_get_rules_for_topic_empty(
        self,
        rule_extractor: RuleExtractor,
        mock_connection: MagicMock,
    ) -> None:
        """Test getting rules when none exist for topic."""
        mock_connection.execute_query.return_value = []

        results = rule_extractor.get_rules_for_topic("unknown topic")

        assert results == []

    def test_get_rules_for_topic_exception(
        self,
        rule_extractor: RuleExtractor,
        mock_connection: MagicMock,
    ) -> None:
        """Test get_rules_for_topic handles exceptions gracefully."""
        mock_connection.execute_query.side_effect = Exception("Database error")

        results = rule_extractor.get_rules_for_topic("test topic")

        assert results == []

    def test_get_similar_rules(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test getting similar rules via vector search."""
        expected_results = [
            {"content": "Rule A", "score": 0.9},
            {"content": "Rule B", "score": 0.85},
        ]
        mock_vector_engine.search_similar.return_value = expected_results

        results = rule_extractor.get_similar_rules("test query", k=3)

        assert results == expected_results
        mock_vector_engine.search_similar.assert_called_once_with("test query", k=3)

    def test_generate_qa_context_no_rules(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test context generation when no rules found."""
        mock_vector_engine.search_similar.return_value = []

        result = rule_extractor.generate_qa_context("test query")

        assert result == ""

    def test_generate_qa_context_with_rules(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test context generation with rules."""
        mock_vector_engine.search_similar.return_value = [
            {"content": "Rule content 1", "metadata": {}},
            {"content": "Rule content 2", "metadata": {}},
        ]

        result = rule_extractor.generate_qa_context("test query", max_rules=2)

        assert "## Relevant Rules" in result
        assert "### Rule 1" in result
        assert "Rule content 1" in result
        assert "### Rule 2" in result
        assert "Rule content 2" in result

    def test_generate_qa_context_with_examples(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test context generation includes examples when available."""
        mock_vector_engine.search_similar.return_value = [
            {
                "content": "Rule with examples",
                "metadata": {"examples": ["Example 1", "Example 2", "Example 3"]},
            },
        ]

        result = rule_extractor.generate_qa_context(
            "test query",
            include_examples=True,
        )

        assert "**Examples:**" in result
        assert "- Example 1" in result
        assert "- Example 2" in result
        # Only first 2 examples should be included
        assert "- Example 3" not in result

    def test_generate_qa_context_without_examples(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test context generation excludes examples when disabled."""
        mock_vector_engine.search_similar.return_value = [
            {
                "content": "Rule content",
                "metadata": {"examples": ["Example 1"]},
            },
        ]

        result = rule_extractor.generate_qa_context(
            "test query",
            include_examples=False,
        )

        assert "**Examples:**" not in result
        assert "Example 1" not in result

    def test_validate_answer_against_rules(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test answer validation against rules."""
        mock_vector_engine.search_similar.return_value = [
            {"content": "Rule 1"},
            {"content": "Rule 2"},
            {"content": "Rule 3"},
        ]

        result = rule_extractor.validate_answer_against_rules(
            answer="Test answer",
            query="Test query",
        )

        assert "valid" in result
        assert result["valid"] is True
        assert "violations" in result
        assert result["violations"] == []
        assert "rules_checked" in result
        assert result["rules_checked"] == 3

    def test_validate_answer_no_rules(
        self,
        rule_extractor: RuleExtractor,
        mock_vector_engine: MagicMock,
    ) -> None:
        """Test answer validation when no rules found."""
        mock_vector_engine.search_similar.return_value = []

        result = rule_extractor.validate_answer_against_rules(
            answer="Test answer",
            query="Test query",
        )

        assert result["valid"] is True
        assert result["rules_checked"] == 0
