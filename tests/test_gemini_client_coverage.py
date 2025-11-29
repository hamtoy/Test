from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from google.api_core import exceptions as google_exceptions
from src import gemini_model_client as gmc


class TestGeminiModelClientBehaviors:
    """Test GeminiModelClient with mocked API."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Setup mocks for all tests in this class."""
        # Mock environment variable
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        # Mock google.generativeai
        self.mock_model = MagicMock()
        self.mock_response = MagicMock()
        self.mock_response.text = "Test response"
        self.mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        self.mock_model.generate_content.return_value = self.mock_response

        with (
            patch("google.generativeai.GenerativeModel", return_value=self.mock_model),
            patch("google.generativeai.configure"),
        ):
            yield

    def test_gemini_model_client_behaviors(self):
        client = gmc.GeminiModelClient()

        # Test generate
        self.mock_response.text = "LLM:hello"
        result = client.generate("hello")
        assert result.startswith("LLM:")
        self.mock_model.generate_content.assert_called()

        # Test evaluate (empty)
        self.mock_response.text = "invalid json"
        empty_eval = client.evaluate("q", [])
        assert empty_eval["best_answer"] is None

        # Test evaluate (length based fallback)
        self.mock_response.text = "not numbers"
        length_eval = client.evaluate("q", ["a", "bb"])
        assert length_eval["best_index"] == 1

        # Test evaluate (parsed)
        self.mock_response.text = "점수1: 2\n점수2: 4\n점수3: 1\n최고: 2"
        parsed_eval = client.evaluate("q", ["a", "bb", "ccc"])
        assert parsed_eval["best_index"] == 1

        # Test rewrite
        self.mock_response.text = "rewritten text"
        assert client.rewrite("orig").startswith("rewritten")

    def test_gemini_model_client_errors(self):
        client = gmc.GeminiModelClient()

        # Mock exception
        self.mock_model.generate_content.side_effect = google_exceptions.GoogleAPIError(
            "boom"
        )

        # generate handles exceptions
        assert client.generate("hi").startswith("[생성 실패")

        # Reset side effect for next calls
        self.mock_model.generate_content.side_effect = None

        # evaluate len-based fallback on parse failure is already tested above

        # rewrite/fact_check exception paths
        self.mock_model.generate_content.side_effect = google_exceptions.GoogleAPIError(
            "rewriter error"
        )
        res = client.rewrite("text")
        assert "실패" in res
        assert "rewriter error" in res

    def test_gemini_model_client_type_error(self):
        client = gmc.GeminiModelClient()

        # Make the mock raise TypeError
        self.mock_model.generate_content.side_effect = TypeError("bad type")

        # Test with invalid input type
        # The client catches TypeError and returns an error string
        res = client.generate(12345)  # type: ignore[arg-type]
        assert "생성 실패" in res
        assert "입력 오류" in res
