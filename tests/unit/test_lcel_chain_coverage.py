"""Tests for src/llm/lcel_chain.py to increase coverage."""

from typing import List
from unittest.mock import MagicMock, Mock, patch


from src.llm.lcel_chain import LCELOptimizedChain


class TestLCELChainCoverage:
    """Test LCELOptimizedChain uncovered lines."""

    @patch("src.llm.lcel_chain.GeminiModelClient")
    def test_get_rules_exception(self, mock_client: MagicMock) -> None:
        """Test _get_rules handles exceptions."""
        mock_kg = MagicMock()
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("DB error")
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_kg.session.return_value = mock_session

        chain = LCELOptimizedChain(kg=mock_kg)
        result: List[str] = chain._get_rules({"query_type": "explanation"})

        assert result == []

    @patch("src.llm.lcel_chain.GeminiModelClient")
    def test_get_examples_exception(self, mock_client: MagicMock) -> None:
        """Test _get_examples handles exceptions."""
        mock_kg = MagicMock()
        mock_kg.get_examples.side_effect = Exception("DB error")

        chain = LCELOptimizedChain(kg=mock_kg)
        result: List[str] = chain._get_examples({})

        assert result == []

    @patch("src.llm.lcel_chain.GeminiModelClient")
    def test_get_constraints_exception(self, mock_client: MagicMock) -> None:
        """Test _get_constraints handles exceptions."""
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type.side_effect = Exception("DB error")

        chain = LCELOptimizedChain(kg=mock_kg)
        result: List[str] = chain._get_constraints({"query_type": "explanation"})

        assert result == []

    @patch("src.llm.lcel_chain.GeminiModelClient")
    def test_get_examples_success(self, mock_client: MagicMock) -> None:
        """Test _get_examples returns examples."""
        mock_kg = MagicMock()
        mock_kg.get_examples.return_value = [
            {"text": "Example 1"},
            {"text": "Example 2"},
        ]

        chain = LCELOptimizedChain(kg=mock_kg)
        result: List[str] = chain._get_examples({})

        assert result == ["Example 1", "Example 2"]

    @patch("src.llm.lcel_chain.GeminiModelClient")
    def test_get_constraints_success(self, mock_client: MagicMock) -> None:
        """Test _get_constraints returns constraints."""
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type.return_value = [
            {"description": "Constraint 1"},
            {"description": "Constraint 2"},
        ]

        chain = LCELOptimizedChain(kg=mock_kg)
        result: List[str] = chain._get_constraints({"query_type": "explanation"})

        assert result == ["Constraint 1", "Constraint 2"]
