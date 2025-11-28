"""Tests for processing/context_augmentation.py module to improve coverage."""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


class TestAdvancedContextAugmentation:
    """Tests for AdvancedContextAugmentation class."""

    def test_init_without_gemini_key(self):
        """Test initialization without Gemini API key (no vector index)."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph.return_value = MagicMock()

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                assert aug.vector_index is None
                mock_graph.assert_called_once()

    def test_init_with_gemini_key(self):
        """Test initialization with Gemini API key (creates vector index)."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                mock_graph.return_value = MagicMock()
                mock_vector.from_existing_graph.return_value = MagicMock()

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key="AIza" + "0" * 35,
                )

                assert aug.vector_index is not None
                mock_vector.from_existing_graph.assert_called_once()

    def test_init_with_env_gemini_key(self, monkeypatch):
        """Test initialization uses GEMINI_API_KEY from environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "0" * 35)

        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                mock_graph.return_value = MagicMock()
                mock_vector.from_existing_graph.return_value = MagicMock()

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                )

                assert aug.vector_index is not None


class TestAugmentPromptWithSimilarCases:
    """Tests for augment_prompt_with_similar_cases method."""

    def test_augment_with_vector_index(self):
        """Test augmentation with vector index available."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                # Setup mocks
                mock_graph_instance = MagicMock()
                mock_graph.return_value = mock_graph_instance

                mock_vector_instance = MagicMock()
                mock_vector.from_existing_graph.return_value = mock_vector_instance

                # Mock similarity search results
                mock_doc1 = MagicMock()
                mock_doc1.page_content = "유사 블록 1"
                mock_doc1.metadata = {"id": 1}

                mock_doc2 = MagicMock()
                mock_doc2.page_content = "유사 블록 2"
                mock_doc2.metadata = {"id": 2}

                mock_vector_instance.similarity_search.return_value = [mock_doc1, mock_doc2]

                # Mock session and query result
                mock_session = MagicMock()
                mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                    return_value=mock_session
                )
                mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                    return_value=False
                )

                mock_result = MagicMock()
                mock_result.data.return_value = [
                    {"rule": "규칙 1", "priority": 1, "examples": ["예시 1"]},
                ]
                mock_session.run.return_value = mock_result

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key="AIza" + "0" * 35,
                )

                result = aug.augment_prompt_with_similar_cases(
                    user_query="테스트 질의", query_type="explanation"
                )

                assert "similar_cases" in result
                assert "relevant_rules" in result
                assert "query_type" in result
                assert result["query_type"] == "explanation"

    def test_augment_without_vector_index_fallback(self):
        """Test augmentation falls back to graph search when no vector index."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            # Mock session for fallback graph query
            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            mock_record = MagicMock()
            mock_record.get.side_effect = lambda key: {
                "blocks": [{"content": "블록 내용"}],
                "rules": [{"rule": "규칙", "priority": 1, "examples": []}],
            }.get(key)

            mock_result = MagicMock()
            mock_result.single.return_value = mock_record
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.augment_prompt_with_similar_cases(
                    user_query="테스트 질의", query_type="summary"
                )

                assert "similar_cases" in result
                assert "relevant_rules" in result

    def test_augment_fallback_exception_handling(self):
        """Test augmentation handles fallback query exceptions."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            # Mock session to raise exception
            mock_session = MagicMock()
            mock_session.run.side_effect = Exception("Query failed")
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                # Should not raise, should return empty results
                result = aug.augment_prompt_with_similar_cases(
                    user_query="테스트", query_type="explanation"
                )

                assert result["similar_cases"] == []
                assert result["relevant_rules"] == []

    def test_augment_with_empty_block_ids(self):
        """Test augmentation when similarity search returns docs without metadata ids."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                mock_graph_instance = MagicMock()
                mock_graph.return_value = mock_graph_instance

                mock_vector_instance = MagicMock()
                mock_vector.from_existing_graph.return_value = mock_vector_instance

                # Mock doc without id in metadata
                mock_doc = MagicMock()
                mock_doc.page_content = "내용"
                mock_doc.metadata = {}  # No id

                mock_vector_instance.similarity_search.return_value = [mock_doc]

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key="AIza" + "0" * 35,
                )

                result = aug.augment_prompt_with_similar_cases(
                    user_query="테스트", query_type="explanation"
                )

                # Should still return results, just empty rules since no block_ids
                assert "similar_cases" in result
                assert "relevant_rules" in result

    def test_augment_fallback_no_record(self):
        """Test augmentation when fallback query returns no record."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            mock_result = MagicMock()
            mock_result.single.return_value = None
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.augment_prompt_with_similar_cases(
                    user_query="테스트", query_type="summary"
                )

                assert result["similar_cases"] == []
                assert result["relevant_rules"] == []


class TestGenerateWithAugmentation:
    """Tests for generate_with_augmentation method."""

    def test_generate_with_augmentation_basic(self):
        """Test generate_with_augmentation returns formatted prompt."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            # Mock session for fallback (since no gemini key)
            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            mock_result = MagicMock()
            mock_result.single.return_value = None
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.generate_with_augmentation(
                    user_query="사용자 질의",
                    query_type="explanation",
                    base_context={"key": "value"},
                )

                assert isinstance(result, str)
                assert "사용자 질의" in result
                assert "explanation" in result

    def test_generate_with_augmentation_with_results(self):
        """Test generate_with_augmentation includes similar cases and rules."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                mock_graph_instance = MagicMock()
                mock_graph.return_value = mock_graph_instance

                mock_vector_instance = MagicMock()
                mock_vector.from_existing_graph.return_value = mock_vector_instance

                # Mock similarity search with content
                mock_doc = MagicMock()
                mock_doc.page_content = "A" * 150  # Long content to test truncation
                mock_doc.metadata = {"id": 1}

                mock_vector_instance.similarity_search.return_value = [mock_doc]

                # Mock session
                mock_session = MagicMock()
                mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                    return_value=mock_session
                )
                mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                    return_value=False
                )

                mock_result = MagicMock()
                mock_result.data.return_value = [
                    {"rule": "중요한 규칙", "priority": 1, "examples": ["예시 1", "예시 2"]},
                ]
                mock_session.run.return_value = mock_result

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key="AIza" + "0" * 35,
                )

                result = aug.generate_with_augmentation(
                    user_query="테스트 질의",
                    query_type="reasoning",
                    base_context={"context": "테스트"},
                )

                assert "테스트 질의" in result
                assert "reasoning" in result
                # Should include truncated similar case
                assert "..." in result or "중요한 규칙" in result

    def test_generate_with_augmentation_empty_results(self):
        """Test generate_with_augmentation handles empty results gracefully."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            mock_result = MagicMock()
            mock_result.single.return_value = None
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.generate_with_augmentation(
                    user_query="테스트",
                    query_type="summary",
                    base_context={},
                )

                # Should contain "(none)" for empty sections
                assert "(none)" in result


class TestSimilarCasesExtraction:
    """Tests for similar cases extraction from different document types."""

    def test_extract_from_page_content(self):
        """Test extracting content from page_content attribute."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            with patch("src.processing.context_augmentation.Neo4jVector") as mock_vector:
                mock_graph_instance = MagicMock()
                mock_graph.return_value = mock_graph_instance

                mock_vector_instance = MagicMock()
                mock_vector.from_existing_graph.return_value = mock_vector_instance

                # Document with page_content
                mock_doc = MagicMock()
                mock_doc.page_content = "페이지 콘텐츠"
                mock_doc.metadata = {}

                mock_vector_instance.similarity_search.return_value = [mock_doc]

                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key="AIza" + "0" * 35,
                )

                result = aug.augment_prompt_with_similar_cases("테스트", "explanation")

                assert "페이지 콘텐츠" in result["similar_cases"]

    def test_extract_from_dict_content(self):
        """Test extracting content from dict with 'content' key."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            # Return dict-like blocks
            mock_record = MagicMock()
            mock_record.get.side_effect = lambda key: {
                "blocks": [{"content": "딕셔너리 콘텐츠"}],
                "rules": [],
            }.get(key)

            mock_result = MagicMock()
            mock_result.single.return_value = mock_record
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.augment_prompt_with_similar_cases("테스트", "summary")

                assert "딕셔너리 콘텐츠" in result["similar_cases"]

    def test_extract_from_dict_text(self):
        """Test extracting content from dict with 'text' key."""
        with patch("src.processing.context_augmentation.Neo4jGraph") as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            mock_session = MagicMock()
            mock_graph_instance._driver.session.return_value.__enter__ = MagicMock(
                return_value=mock_session
            )
            mock_graph_instance._driver.session.return_value.__exit__ = MagicMock(
                return_value=False
            )

            # Return dict-like blocks with 'text' key
            mock_record = MagicMock()
            mock_record.get.side_effect = lambda key: {
                "blocks": [{"text": "텍스트 내용"}],
                "rules": [],
            }.get(key)

            mock_result = MagicMock()
            mock_result.single.return_value = mock_record
            mock_session.run.return_value = mock_result

            with patch.dict("os.environ", {}, clear=True):
                from src.processing.context_augmentation import AdvancedContextAugmentation

                aug = AdvancedContextAugmentation(
                    neo4j_uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                    gemini_key=None,
                )

                result = aug.augment_prompt_with_similar_cases("테스트", "summary")

                assert "텍스트 내용" in result["similar_cases"]
