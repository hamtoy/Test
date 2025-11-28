"""Tests for graph/builder.py module to improve coverage."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest


class TestQAGraphBuilder:
    """Tests for QAGraphBuilder class."""

    def test_init_creates_driver(self):
        """Test __init__ creates driver with correct auth."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            mock_gd.driver.assert_called_once_with(
                "bolt://localhost:7687", auth=("neo4j", "password")
            )
            assert builder.driver == mock_driver

    def test_close_closes_driver(self):
        """Test close method closes the driver."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")
            builder.close()

            mock_driver.close.assert_called_once()

    def test_create_schema_constraints(self):
        """Test create_schema_constraints creates all constraints."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")
            builder.create_schema_constraints()

            # Should run 7 constraint creation queries
            assert mock_session.run.call_count == 7

    def test_extract_query_types(self):
        """Test extract_query_types creates QueryType nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder, QUERY_TYPES

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.extract_query_types()

            # Should run one query per query type
            assert mock_session.run.call_count == len(QUERY_TYPES)

    def test_extract_constraints(self):
        """Test extract_constraints creates Constraint nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder, CONSTRAINTS

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.extract_constraints()

            assert mock_session.run.call_count == len(CONSTRAINTS)

    def test_link_rules_to_constraints(self):
        """Test link_rules_to_constraints creates relationships."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            # Mock the count result
            mock_result = MagicMock()
            mock_result.single.return_value = {"links": 5}
            mock_session.run.return_value = mock_result

            from src.graph.builder import QAGraphBuilder, CONSTRAINT_KEYWORDS

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.link_rules_to_constraints()

            # Should run base query + one per keyword + count query
            expected_calls = 1 + len(CONSTRAINT_KEYWORDS) + 1
            assert mock_session.run.call_count == expected_calls

    def test_link_rules_to_constraints_no_result(self):
        """Test link_rules_to_constraints handles None result."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            # Mock result returning None for single()
            mock_result = MagicMock()
            mock_result.single.return_value = None
            mock_session.run.return_value = mock_result

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with pytest.raises(RuntimeError, match="Failed to count rule-constraint links"):
                builder.link_rules_to_constraints()

    def test_extract_examples(self):
        """Test extract_examples creates Example nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            # Mock the query result
            mock_records = [
                {"text": "❌ 잘못된 예시", "type": "negative"},
                {"text": "⭕ 올바른 예시", "type": "positive"},
            ]
            mock_result = MagicMock()
            mock_result.__iter__ = MagicMock(return_value=iter(mock_records))
            mock_session.run.return_value = mock_result

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.extract_examples()

            # Should run initial query + MERGE for each example
            assert mock_session.run.call_count >= 1

    def test_link_examples_to_rules(self):
        """Test link_examples_to_rules creates relationships."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            mock_result = MagicMock()
            mock_result.single.return_value = {"links": 10}
            mock_session.run.return_value = mock_result

            from src.graph.builder import QAGraphBuilder, EXAMPLE_RULE_MAPPINGS

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.link_examples_to_rules()

            # Should run DEMONSTRATES + VIOLATES + manual mappings + count
            expected_min_calls = 2 + len(EXAMPLE_RULE_MAPPINGS) + 1
            assert mock_session.run.call_count >= expected_min_calls

    def test_link_examples_to_rules_no_result(self):
        """Test link_examples_to_rules handles None result."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            mock_result = MagicMock()
            mock_result.single.return_value = None
            mock_session.run.return_value = mock_result

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with pytest.raises(RuntimeError, match="Failed to count example-rule links"):
                builder.link_examples_to_rules()

    def test_create_templates(self):
        """Test create_templates creates Template nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.create_templates()

            # Should call session.run multiple times
            assert mock_session.run.call_count > 0

    def test_create_error_patterns(self):
        """Test create_error_patterns creates ErrorPattern nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder, ERROR_PATTERNS

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.create_error_patterns()

            assert mock_session.run.call_count == len(ERROR_PATTERNS)

    def test_create_best_practices(self):
        """Test create_best_practices creates BestPractice nodes."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder, BEST_PRACTICES

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.create_best_practices()

            # Should run 2 queries per best practice (CREATE + LINK)
            assert mock_session.run.call_count == len(BEST_PRACTICES) * 2

    def test_link_rules_to_query_types(self):
        """Test link_rules_to_query_types creates relationships."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            from src.graph.builder import QAGraphBuilder, QUERY_TYPE_KEYWORDS

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.link_rules_to_query_types()

            assert mock_session.run.call_count == len(QUERY_TYPE_KEYWORDS)


class TestRequireEnv:
    """Tests for require_env function."""

    def test_require_env_exists(self, monkeypatch):
        """Test require_env returns value when env var exists."""
        from src.graph.builder import require_env

        monkeypatch.setenv("TEST_VAR", "test_value")
        result = require_env("TEST_VAR")
        assert result == "test_value"

    def test_require_env_missing(self, monkeypatch):
        """Test require_env raises when env var missing."""
        from src.graph.builder import require_env

        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(EnvironmentError, match="MISSING_VAR"):
            require_env("MISSING_VAR")

    def test_require_env_empty(self, monkeypatch):
        """Test require_env raises when env var is empty."""
        from src.graph.builder import require_env

        monkeypatch.setenv("EMPTY_VAR", "")
        with pytest.raises(EnvironmentError, match="EMPTY_VAR"):
            require_env("EMPTY_VAR")


class TestExtractRulesFromNotion:
    """Tests for extract_rules_from_notion method."""

    def test_extract_rules_from_notion_with_headings(self):
        """Test extract_rules_from_notion processes headings correctly."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            # Mock headings query
            mock_headings_result = MagicMock()
            mock_headings_result.data.return_value = [
                {
                    "page_id": "page1",
                    "start_order": 0,
                    "section": "자주 틀리는 패턴",
                }
            ]

            # Mock siblings query - returns iterator of records
            mock_sibling1 = {"id": "b1", "content": "규칙 내용 길이가 10자 이상입니다", "type": "paragraph"}
            mock_sibling2 = {"id": "b2", "content": "또 다른 규칙입니다 길이가 충분함", "type": "bulleted_list_item"}
            mock_siblings_result = MagicMock()
            mock_siblings_result.__iter__ = MagicMock(return_value=iter([mock_sibling1, mock_sibling2]))

            # Set up the mock to return different results for different queries
            # First call returns headings, second returns siblings, then MERGE calls return None
            mock_session.run.side_effect = [
                mock_headings_result,
                mock_siblings_result,
                None,  # First MERGE for rule
                None,  # Second MERGE for rule
            ]

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.extract_rules_from_notion()

    def test_extract_rules_skips_short_content(self):
        """Test extract_rules_from_notion skips content <= 10 chars."""
        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            mock_headings_result = MagicMock()
            mock_headings_result.data.return_value = [
                {"page_id": "page1", "start_order": 0, "section": "자주 틀리는"}
            ]

            mock_siblings_result = MagicMock()
            mock_siblings_result.__iter__ = MagicMock(
                return_value=iter([{"id": "b1", "content": "짧은", "type": "paragraph"}])
            )

            mock_session.run.side_effect = [mock_headings_result, mock_siblings_result]

            from src.graph.builder import QAGraphBuilder

            builder = QAGraphBuilder("bolt://localhost:7687", "neo4j", "password")

            with patch("builtins.print"):
                builder.extract_rules_from_notion()

            # Should only call run twice (headings + siblings), no rule creation
            assert mock_session.run.call_count == 2


class TestMainFunction:
    """Tests for main function."""

    def test_main_success(self, monkeypatch):
        """Test main function runs successfully."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        with patch("src.graph.builder.GraphDatabase") as mock_gd:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_gd.driver.return_value = mock_driver

            # Mock all query results
            mock_result = MagicMock()
            mock_result.single.return_value = {"links": 0}
            mock_result.data.return_value = []
            mock_result.__iter__ = MagicMock(return_value=iter([]))
            mock_session.run.return_value = mock_result

            from src.graph.builder import main

            with patch("builtins.print"):
                main()

            mock_driver.close.assert_called()

    def test_main_missing_env(self, monkeypatch):
        """Test main function exits on missing env vars."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        from src.graph.builder import main

        with pytest.raises(EnvironmentError):
            main()
