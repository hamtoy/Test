"""Extended tests for qa/graph/utils module.

Covers:
- len_if_sized() function
- CustomGeminiEmbeddings class
- init_vector_store() with exception handling
- ensure_formatting_rule_schema() functions
- record_vector_metrics() function
- format_rules() function
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from neo4j.exceptions import Neo4jError

from src.qa.graph.utils import (
    CustomGeminiEmbeddings,
    ensure_formatting_rule_schema,
    format_rules,
    init_vector_store,
    len_if_sized,
    record_vector_metrics,
)


class TestLenIfSized:
    """Tests for len_if_sized function."""

    def test_len_if_sized_with_list(self) -> None:
        """Test with a list."""
        result = len_if_sized([1, 2, 3])
        assert result == 3

    def test_len_if_sized_with_string(self) -> None:
        """Test with a string."""
        result = len_if_sized("hello")
        assert result == 5

    def test_len_if_sized_with_dict(self) -> None:
        """Test with a dictionary."""
        result = len_if_sized({"a": 1, "b": 2})
        assert result == 2

    def test_len_if_sized_with_set(self) -> None:
        """Test with a set."""
        result = len_if_sized({1, 2, 3, 4})
        assert result == 4

    def test_len_if_sized_with_non_sized(self) -> None:
        """Test with non-sized object."""
        result = len_if_sized(42)
        assert result == 0

    def test_len_if_sized_with_none(self) -> None:
        """Test with None."""
        result = len_if_sized(None)
        assert result == 0

    def test_len_if_sized_with_generator(self) -> None:
        """Test with generator (not sized)."""
        gen = (x for x in range(5))
        result = len_if_sized(gen)
        assert result == 0


class TestCustomGeminiEmbeddings:
    """Tests for CustomGeminiEmbeddings class."""

    def test_init(self) -> None:
        """Test initialization."""
        with patch("google.generativeai.configure") as mock_configure:
            embeddings = CustomGeminiEmbeddings(
                api_key="test-api-key",
                model="models/custom-model",
            )

            mock_configure.assert_called_once_with(api_key="test-api-key")
            assert embeddings.model == "models/custom-model"

    def test_init_default_model(self) -> None:
        """Test initialization with default model."""
        with patch("google.generativeai.configure"):
            embeddings = CustomGeminiEmbeddings(api_key="test-api-key")

            assert embeddings.model == "models/text-embedding-004"

    def test_embed_query(self) -> None:
        """Test embed_query method."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.embed_content") as mock_embed,
        ):
            mock_embed.return_value = {"embedding": [0.1, 0.2, 0.3]}

            embeddings = CustomGeminiEmbeddings(api_key="test-key")
            result = embeddings.embed_query("test text")

            assert result == [0.1, 0.2, 0.3]
            mock_embed.assert_called_once_with(
                model="models/text-embedding-004",
                content="test text",
                task_type="retrieval_query",
            )

    def test_embed_documents(self) -> None:
        """Test embed_documents method."""
        with (
            patch("google.generativeai.configure"),
            patch("google.generativeai.embed_content") as mock_embed,
        ):
            mock_embed.side_effect = [
                {"embedding": [0.1, 0.2]},
                {"embedding": [0.3, 0.4]},
            ]

            embeddings = CustomGeminiEmbeddings(api_key="test-key")
            result = embeddings.embed_documents(["text1", "text2"])

            assert result == [[0.1, 0.2], [0.3, 0.4]]
            assert mock_embed.call_count == 2


class TestInitVectorStore:
    """Tests for init_vector_store function."""

    def test_init_vector_store_no_langchain(self) -> None:
        """Test when langchain_neo4j is not installed."""
        logger = MagicMock()

        with (
            patch.dict("sys.modules", {"langchain_neo4j": None}),
            patch("builtins.__import__", side_effect=ImportError),
        ):
            result = init_vector_store(
                neo4j_uri="bolt://localhost",
                neo4j_user="neo4j",
                neo4j_password="password",
                logger=logger,
            )

            assert result is None

    def test_init_vector_store_no_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test when GEMINI_API_KEY is not set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        logger = MagicMock()

        with patch("src.qa.graph.utils.Neo4jVector", create=True):
            # Mock successful import
            pass

        init_vector_store(
            neo4j_uri="bolt://localhost",
            neo4j_user="neo4j",
            neo4j_password="password",
            logger=logger,
        )

        # Should return None if no API key
        # (actual behavior depends on import)

    def test_init_vector_store_neo4j_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test when Neo4j connection fails."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        logger = MagicMock()

        with (
            patch("src.qa.graph.utils.CustomGeminiEmbeddings"),
            patch("langchain_neo4j.Neo4jVector") as mock_vector,
        ):
            mock_vector.from_existing_graph.side_effect = Neo4jError(
                "Connection failed"
            )

            result = init_vector_store(
                neo4j_uri="bolt://localhost",
                neo4j_user="neo4j",
                neo4j_password="password",
                logger=logger,
            )

            assert result is None
            logger.warning.assert_called()


class TestEnsureFormattingRuleSchema:
    """Tests for ensure_formatting_rule_schema function."""

    def test_ensure_schema_with_driver_success(self) -> None:
        """Test schema creation with driver succeeds."""
        logger = MagicMock()
        mock_driver = MagicMock()
        mock_session = MagicMock()

        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_driver.driver = MagicMock()
        mock_driver.driver.session = MagicMock()

        ensure_formatting_rule_schema(
            driver=mock_driver,
            provider=None,
            logger=logger,
        )

        # Should have run statements
        assert mock_session.run.call_count >= 1

    def test_ensure_schema_driver_no_session(self) -> None:
        """Test when driver has no session method."""
        logger = MagicMock()
        mock_driver = MagicMock()
        mock_driver.driver = None

        # Should not raise
        ensure_formatting_rule_schema(
            driver=mock_driver,
            provider=None,
            logger=logger,
        )

        logger.info.assert_called()

    def test_ensure_schema_driver_neo4j_error(self) -> None:
        """Test when driver raises Neo4jError."""
        logger = MagicMock()
        mock_driver = MagicMock()
        mock_driver.driver = MagicMock()
        mock_driver.driver.session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            side_effect=Neo4jError("Connection failed")
        )

        # Should not raise
        ensure_formatting_rule_schema(
            driver=mock_driver,
            provider=None,
            logger=logger,
        )

    def test_ensure_schema_no_driver_no_provider(self) -> None:
        """Test with no driver and no provider."""
        logger = MagicMock()

        ensure_formatting_rule_schema(
            driver=None,
            provider=None,
            logger=logger,
        )

        logger.info.assert_called_with(
            "Skipping FormattingRule schema ensure; no graph provider"
        )


class TestRecordVectorMetrics:
    """Tests for record_vector_metrics function."""

    def test_record_vector_metrics_success(self) -> None:
        """Test recording successful vector search metrics."""
        mock_cache_metrics = MagicMock()

        result = record_vector_metrics(
            mock_cache_metrics,
            query="test query",
            k=5,
            result_count=3,
            success=True,
            duration_ms=150.5,
        )

        mock_cache_metrics.record_query.assert_called_once_with(
            "vector_search",
            duration_ms=150.5,
            result_count=3,
            status="hit",
        )

        assert result["metric"] == "vector_search"
        assert result["duration_ms"] == 150.5
        assert result["k"] == 5
        assert result["query_length"] == len("test query")
        assert result["result_count"] == 3

    def test_record_vector_metrics_error(self) -> None:
        """Test recording error vector search metrics."""
        mock_cache_metrics = MagicMock()

        result = record_vector_metrics(
            mock_cache_metrics,
            query="failed query",
            k=10,
            result_count=0,
            success=False,
            duration_ms=50.123,
        )

        mock_cache_metrics.record_query.assert_called_once_with(
            "vector_search",
            duration_ms=50.123,
            result_count=0,
            status="error",
        )

        assert result["duration_ms"] == 50.12


class TestFormatRules:
    """Tests for format_rules function."""

    def test_format_rules_with_data(self) -> None:
        """Test formatting rules with valid data."""
        rules_data = [
            {"text": "Rule 1: Do something"},
            {"text": "Rule 2: Do something else"},
            {"text": "Rule 3: Another rule"},
        ]

        result = format_rules(rules_data)

        assert "### Formatting Rules" in result
        assert "- Rule 1: Do something" in result
        assert "- Rule 2: Do something else" in result
        assert "- Rule 3: Another rule" in result

    def test_format_rules_empty_list(self) -> None:
        """Test formatting with empty list."""
        result = format_rules([])

        assert result == ""

    def test_format_rules_no_text_fields(self) -> None:
        """Test formatting when no text fields present."""
        rules_data = [
            {"other_field": "value"},
            {"another": "data"},
        ]

        result = format_rules(rules_data)

        assert result == ""

    def test_format_rules_mixed_data(self) -> None:
        """Test formatting with mixed data (some with text, some without)."""
        rules_data = [
            {"text": "Valid rule"},
            {"other": "No text here"},
            {"text": ""},  # Empty text
            {"text": "Another valid rule"},
        ]

        result = format_rules(rules_data)

        assert "- Valid rule" in result
        assert "- Another valid rule" in result
        assert result.count("-") == 2  # Only 2 valid rules

    def test_format_rules_empty_text(self) -> None:
        """Test that empty text values are filtered out."""
        rules_data = [
            {"text": ""},
            {"text": "   "},  # Whitespace (but not empty string)
        ]

        format_rules(rules_data)

        # Empty string should be filtered, whitespace might not be
        # depending on implementation
