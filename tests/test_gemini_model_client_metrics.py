from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import src.llm.gemini as gmc
from typing import Any, Generator


class TestGeminiModelClientMetrics:
    """Test GeminiModelClient metrics logging with mocked API."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
        """Setup mocks for all tests."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")

        self.mock_model = MagicMock()
        self.mock_response = MagicMock()
        self.mock_response.text = "Mocked response"
        self.mock_response.usage_metadata = MagicMock(
            prompt_token_count=100,
            candidates_token_count=50,
            total_token_count=150,
        )
        self.mock_model.generate_content.return_value = self.mock_response

        self.patcher1 = patch(
            "google.generativeai.GenerativeModel", return_value=self.mock_model
        )
        self.patcher2 = patch("google.generativeai.configure")

        self.patcher1.start()
        self.patcher2.start()

        yield

        self.patcher1.stop()
        self.patcher2.stop()

    def test_generate_logs_metrics(self, caplog: pytest.LogCaptureFixture) -> None:
        client = gmc.GeminiModelClient()

        # Mock log_metrics to capture calls, or use caplog/mocking logger
        # The original test mocked log_metrics function. Let's do that.
        captured = {}

        def _log_metrics(logger: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        with patch("src.llm.gemini.log_metrics", side_effect=_log_metrics):
            result = client.generate("Test prompt")

        assert result == "Mocked response"
        # Verify metrics were logged
        assert captured["prompt_tokens"] == 100
        assert captured["completion_tokens"] == 50

    def test_evaluate_and_rewrite_log_metrics(self) -> None:
        client = gmc.GeminiModelClient()

        captured = []

        def _log_metrics(logger: Any, **kwargs: Any) -> None:
            captured.append(kwargs)

        # Mock evaluate response
        self.mock_model.generate_content.side_effect = [
            MagicMock(
                text="점수1: 1\n점수2: 2\n최고: 2",
                usage_metadata=MagicMock(
                    prompt_token_count=10, candidates_token_count=10
                ),
            ),
            MagicMock(
                text="rewritten",
                usage_metadata=MagicMock(
                    prompt_token_count=20, candidates_token_count=20
                ),
            ),
        ]

        with patch("src.llm.gemini.log_metrics", side_effect=_log_metrics):
            eval_res = client.evaluate("q", ["a", "bb"])
            rewritten = client.rewrite("answer")

        assert eval_res["best_index"] == 1
        assert rewritten == "rewritten"
        assert len(captured) >= 2
