"""Tests for QA graph utilities module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.qa.graph.utils import (
    format_rules,
    len_if_sized,
    record_vector_metrics,
)


class TestLenIfSized:
    """Test len_if_sized utility function."""

    def test_len_if_sized_with_list(self) -> None:
        """Test len_if_sized with a list."""
        assert len_if_sized([1, 2, 3]) == 3
        assert len_if_sized([]) == 0

    def test_len_if_sized_with_string(self) -> None:
        """Test len_if_sized with a string."""
        assert len_if_sized("hello") == 5
        assert len_if_sized("") == 0

    def test_len_if_sized_with_tuple(self) -> None:
        """Test len_if_sized with a tuple."""
        assert len_if_sized((1, 2, 3, 4)) == 4
        assert len_if_sized(()) == 0

    def test_len_if_sized_with_dict(self) -> None:
        """Test len_if_sized with a dict."""
        assert len_if_sized({"a": 1, "b": 2}) == 2
        assert len_if_sized({}) == 0

    def test_len_if_sized_with_set(self) -> None:
        """Test len_if_sized with a set."""
        assert len_if_sized({1, 2, 3}) == 3
        assert len_if_sized(set()) == 0

    def test_len_if_sized_with_non_sized(self) -> None:
        """Test len_if_sized with non-sized objects returns 0."""
        assert len_if_sized(None) == 0
        assert len_if_sized(42) == 0
        assert len_if_sized(3.14) == 0

    def test_len_if_sized_with_custom_sized_object(self) -> None:
        """Test len_if_sized with custom Sized object."""

        class CustomSized:
            def __len__(self) -> int:
                return 10

        obj = CustomSized()
        assert len_if_sized(obj) == 10


class TestRecordVectorMetrics:
    """Test record_vector_metrics function."""

    def test_record_vector_metrics_success(self) -> None:
        """Test recording successful vector search metrics."""
        mock_cache_metrics = Mock()
        query = "test query"
        k = 5
        result_count = 3
        duration_ms = 123.456

        result = record_vector_metrics(
            mock_cache_metrics,
            query=query,
            k=k,
            result_count=result_count,
            success=True,
            duration_ms=duration_ms,
        )

        mock_cache_metrics.record_query.assert_called_once_with(
            "vector_search",
            duration_ms=duration_ms,
            result_count=result_count,
            status="hit",
        )

        assert result["metric"] == "vector_search"
        assert result["duration_ms"] == 123.46  # Rounded to 2 decimals
        assert result["k"] == k
        assert result["query_length"] == len(query)
        assert result["result_count"] == result_count

    def test_record_vector_metrics_error(self) -> None:
        """Test recording failed vector search metrics."""
        mock_cache_metrics = Mock()
        query = "another query"
        k = 10
        result_count = 0
        duration_ms = 50.123

        result = record_vector_metrics(
            mock_cache_metrics,
            query=query,
            k=k,
            result_count=result_count,
            success=False,
            duration_ms=duration_ms,
        )

        mock_cache_metrics.record_query.assert_called_once_with(
            "vector_search",
            duration_ms=duration_ms,
            result_count=result_count,
            status="error",
        )

        assert result["metric"] == "vector_search"
        assert result["duration_ms"] == 50.12
        assert result["k"] == k
        assert result["result_count"] == result_count

    def test_record_vector_metrics_empty_query(self) -> None:
        """Test recording metrics with empty query."""
        mock_cache_metrics = Mock()

        result = record_vector_metrics(
            mock_cache_metrics,
            query="",
            k=5,
            result_count=0,
            success=True,
            duration_ms=10.0,
        )

        assert result["query_length"] == 0

    def test_record_vector_metrics_long_query(self) -> None:
        """Test recording metrics with long query."""
        mock_cache_metrics = Mock()
        long_query = "a" * 1000

        result = record_vector_metrics(
            mock_cache_metrics,
            query=long_query,
            k=5,
            result_count=10,
            success=True,
            duration_ms=200.999,
        )

        assert result["query_length"] == 1000
        assert result["duration_ms"] == 201.0  # Rounded up


class TestFormatRules:
    """Test format_rules function."""

    def test_format_rules_empty_list(self) -> None:
        """Test format_rules with empty list."""
        assert format_rules([]) == ""

    def test_format_rules_single_rule(self) -> None:
        """Test format_rules with single rule."""
        rules_data = [{"text": "Use proper grammar"}]
        result = format_rules(rules_data)

        assert "### Formatting Rules" in result
        assert "- Use proper grammar" in result

    def test_format_rules_multiple_rules(self) -> None:
        """Test format_rules with multiple rules."""
        rules_data = [
            {"text": "Rule 1: No markdown"},
            {"text": "Rule 2: Be concise"},
            {"text": "Rule 3: Use periods"},
        ]
        result = format_rules(rules_data)

        assert "### Formatting Rules" in result
        assert "- Rule 1: No markdown" in result
        assert "- Rule 2: Be concise" in result
        assert "- Rule 3: Use periods" in result

    def test_format_rules_missing_text_field(self) -> None:
        """Test format_rules with rules missing text field."""
        rules_data = [
            {"text": "Valid rule"},
            {"description": "No text field"},
            {"text": "Another valid rule"},
        ]
        result = format_rules(rules_data)

        assert "- Valid rule" in result
        assert "- Another valid rule" in result
        assert "description" not in result

    def test_format_rules_empty_text(self) -> None:
        """Test format_rules with empty text values."""
        rules_data = [
            {"text": ""},
            {"text": "Valid rule"},
            {"text": ""},
        ]
        result = format_rules(rules_data)

        assert "- Valid rule" in result
        # Should only have one rule line
        assert result.count("- ") == 1

    def test_format_rules_all_empty_text(self) -> None:
        """Test format_rules when all text fields are empty."""
        rules_data = [
            {"text": ""},
            {"text": ""},
        ]
        result = format_rules(rules_data)

        assert result == ""

    def test_format_rules_no_text_field_at_all(self) -> None:
        """Test format_rules when no rules have text field."""
        rules_data = [
            {"description": "Rule 1"},
            {"name": "Rule 2"},
        ]
        result = format_rules(rules_data)

        assert result == ""

    def test_format_rules_markdown_structure(self) -> None:
        """Test format_rules produces correct markdown structure."""
        rules_data = [
            {"text": "First rule"},
            {"text": "Second rule"},
        ]
        result = format_rules(rules_data)

        lines = result.split("\n")
        assert lines[0] == "### Formatting Rules"
        assert lines[1] == "- First rule"
        assert lines[2] == "- Second rule"

    def test_format_rules_with_extra_fields(self) -> None:
        """Test format_rules ignores extra fields."""
        rules_data = [
            {
                "text": "Important rule",
                "priority": 1,
                "category": "formatting",
                "examples": ["ex1", "ex2"],
            }
        ]
        result = format_rules(rules_data)

        assert "- Important rule" in result
        assert "priority" not in result
        assert "category" not in result


class TestCustomGeminiEmbeddings:
    """Test CustomGeminiEmbeddings class."""

    @patch("src.qa.graph.utils.genai")
    def test_custom_gemini_embeddings_init(self, mock_genai: Mock) -> None:
        """Test CustomGeminiEmbeddings initialization."""
        from src.qa.graph.utils import CustomGeminiEmbeddings

        api_key = "test_api_key"
        embeddings = CustomGeminiEmbeddings(api_key=api_key)

        mock_genai.configure.assert_called_once_with(api_key=api_key)
        assert embeddings.model == "models/text-embedding-004"

    @patch("src.qa.graph.utils.genai")
    def test_custom_gemini_embeddings_custom_model(self, mock_genai: Mock) -> None:
        """Test CustomGeminiEmbeddings with custom model."""
        from src.qa.graph.utils import CustomGeminiEmbeddings

        api_key = "test_api_key"
        custom_model = "models/custom-embedding"
        embeddings = CustomGeminiEmbeddings(api_key=api_key, model=custom_model)

        assert embeddings.model == custom_model

    @patch("src.qa.graph.utils.genai")
    def test_embed_query(self, mock_genai: Mock) -> None:
        """Test embed_query method."""
        from src.qa.graph.utils import CustomGeminiEmbeddings

        mock_genai.embed_content.return_value = {"embedding": [0.1, 0.2, 0.3]}

        embeddings = CustomGeminiEmbeddings(api_key="test_key")
        result = embeddings.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_genai.embed_content.assert_called_once_with(
            model="models/text-embedding-004",
            content="test query",
            task_type="retrieval_query",
        )

    @patch("src.qa.graph.utils.genai")
    def test_embed_documents(self, mock_genai: Mock) -> None:
        """Test embed_documents method."""
        from src.qa.graph.utils import CustomGeminiEmbeddings

        mock_genai.embed_content.side_effect = [
            {"embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]},
            {"embedding": [0.5, 0.6]},
        ]

        embeddings = CustomGeminiEmbeddings(api_key="test_key")
        texts = ["text1", "text2", "text3"]
        result = embeddings.embed_documents(texts)

        assert result == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        assert mock_genai.embed_content.call_count == 3
