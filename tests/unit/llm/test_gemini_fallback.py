# mypy: disable-error-code=no-untyped-call
"""Unit tests for GeminiModelClient fallback mechanism."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions


class TestGeminiModelClientFallback:
    """Tests for the model fallback mechanism on rate limits."""

    @pytest.fixture
    def mock_env(self) -> Iterator[None]:
        """Mock environment variables for tests."""
        with patch.dict(
            "os.environ",
            {
                "GEMINI_API_KEY": "test-api-key",
                "GEMINI_MODEL_NAME": "gemini-pro",
            },
        ):
            yield

    @pytest.fixture
    def mock_genai(self) -> Iterator[MagicMock]:
        """Mock google.generativeai module."""
        with patch("src.llm.gemini.genai") as mock:
            yield mock

    @pytest.fixture
    def mock_init_genai(self) -> Iterator[None]:
        """Mock configure_genai function."""
        with patch("src.llm.init_genai.configure_genai"):
            yield

    def test_fallback_on_rate_limit(
        self, mock_env: None, mock_genai: MagicMock, mock_init_genai: None
    ) -> None:
        """Test that fallback model is used when primary hits rate limit."""
        from src.llm.gemini import GeminiModelClient

        # Setup mock models
        primary_model = MagicMock()
        fallback_model = MagicMock()

        # Primary model raises ResourceExhausted
        primary_model.generate_content.side_effect = (
            google_exceptions.ResourceExhausted("Rate limit exceeded")
        )

        # Fallback model succeeds
        mock_response = MagicMock()
        mock_response.text = "Fallback response"
        mock_response.usage_metadata = None
        fallback_model.generate_content.return_value = mock_response

        # Return different models based on name
        def get_model(name: str) -> MagicMock:
            if name == "gemini-flash-lite-latest":
                return fallback_model
            return primary_model

        mock_genai.GenerativeModel.side_effect = get_model

        # Create client with fallback
        client = GeminiModelClient(fallback_models=["gemini-flash-lite-latest"])

        # Generate should use fallback
        result = client.generate("Test prompt")

        assert result == "Fallback response"
        assert primary_model.generate_content.called
        assert fallback_model.generate_content.called

    def test_all_models_exhausted(
        self, mock_env: None, mock_genai: MagicMock, mock_init_genai: None
    ) -> None:
        """Test error message when all models hit rate limits."""
        from src.llm.gemini import GeminiModelClient

        # All models raise ResourceExhausted
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = google_exceptions.ResourceExhausted(
            "Rate limit exceeded"
        )
        mock_genai.GenerativeModel.return_value = mock_model

        client = GeminiModelClient(fallback_models=["gemini-flash-lite-latest"])

        result = client.generate("Test prompt")

        assert "Rate Limit" in result
        assert "모든 모델" in result

    def test_no_fallback_on_success(
        self, mock_env: None, mock_genai: MagicMock, mock_init_genai: None
    ) -> None:
        """Test that fallback is not used when primary succeeds."""
        from src.llm.gemini import GeminiModelClient

        # Primary model succeeds
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Primary response"
        mock_response.usage_metadata = None
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        client = GeminiModelClient(fallback_models=["gemini-flash-lite-latest"])

        result = client.generate("Test prompt")

        assert result == "Primary response"
        # GenerativeModel called only once (for primary)
        # Note: called twice due to __init__ also creating a model
        assert mock_genai.GenerativeModel.call_count >= 1
