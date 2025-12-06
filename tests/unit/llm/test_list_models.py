"""Tests for LLM list_models module."""

from __future__ import annotations

from unittest.mock import Mock, patch

from src.llm.list_models import list_available_models


class TestListAvailableModels:
    """Test list_available_models function."""

    @patch("src.llm.list_models.genai")
    def test_list_available_models_success(self, mock_genai: Mock) -> None:
        """Test successful model listing."""
        mock_model1 = Mock()
        mock_model1.name = "models/gemini-pro"
        mock_model2 = Mock()
        mock_model2.name = "models/gemini-flash"

        mock_genai.list_models.return_value = [mock_model1, mock_model2]

        result = list_available_models()

        assert len(result) == 2
        assert "models/gemini-pro" in result
        assert "models/gemini-flash" in result

    @patch("src.llm.list_models.genai")
    def test_list_available_models_empty(self, mock_genai: Mock) -> None:
        """Test listing when no models available."""
        mock_genai.list_models.return_value = []

        result = list_available_models()

        assert result == []

    @patch("src.llm.list_models.genai")
    def test_list_available_models_exception(self, mock_genai: Mock) -> None:
        """Test handling of exceptions during model listing."""
        mock_genai.list_models.side_effect = RuntimeError("API error")

        result = list_available_models()

        assert result == []
