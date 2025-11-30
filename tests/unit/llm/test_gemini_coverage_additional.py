"""Additional tests for src/llm/gemini.py to improve coverage."""

from __future__ import annotations

import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import src.llm.gemini as gmc


def _fake_genai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup fake genai module."""

    class _FakeModel:
        def __init__(self, name: str) -> None:
            self.name = name

        def generate_content(
            self, prompt: str, generation_config: Any = None
        ) -> types.SimpleNamespace:
            return types.SimpleNamespace(text="dummy", usage_metadata=None)

    fake = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(name),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
        _logging=None,  # No genai logger
    )
    monkeypatch.setattr(gmc, "genai", fake)


class TestRequireEnv:
    """Test require_env function."""

    def test_require_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing env var raises EnvironmentError."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

        with pytest.raises(EnvironmentError, match="환경 변수"):
            gmc.require_env("NONEXISTENT_VAR")

    def test_require_env_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that present env var is returned."""
        monkeypatch.setenv("TEST_VAR", "test_value")

        result = gmc.require_env("TEST_VAR")
        assert result == "test_value"


class TestGeminiModelClientInit:
    """Test GeminiModelClient initialization."""

    def test_client_with_genai_logger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test client uses genai logger when available."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")

        mock_genai_logger = MagicMock()

        class _FakeModel:
            def __init__(self, name: str) -> None:
                self.name = name

        fake = types.SimpleNamespace(
            configure=lambda api_key: None,
            GenerativeModel=lambda name: _FakeModel(name),
            types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
            _logging=types.SimpleNamespace(logger=mock_genai_logger),
        )
        monkeypatch.setattr(gmc, "genai", fake)

        client = gmc.GeminiModelClient()
        assert client.logger is mock_genai_logger


class TestGeminiModelClientGenerate:
    """Test GeminiModelClient generate method."""

    def test_generate_generic_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test generate handles generic exceptions."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        _fake_genai(monkeypatch)

        client = gmc.GeminiModelClient()

        # Make generate raise a generic exception
        client.model.generate_content = MagicMock(
            side_effect=RuntimeError("unexpected error")
        )

        result = client.generate("test prompt")
        assert "생성 실패(알 수 없음)" in result


class TestGeminiModelClientEvaluate:
    """Test GeminiModelClient evaluate method."""

    def test_evaluate_generic_exception_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test evaluate falls back on generic exception."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        _fake_genai(monkeypatch)

        client = gmc.GeminiModelClient()

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("unexpected")

        client.generate = _raise  # type: ignore[method-assign, assignment]

        result = client.evaluate("question", ["answer1", "answer2"])
        assert result["notes"] == "예상치 못한 오류로 길이 기반 평가 수행"

    def test_evaluate_parse_score_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test evaluate handles malformed score lines."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        _fake_genai(monkeypatch)

        client = gmc.GeminiModelClient()

        # Return malformed score line
        def _generate(*args: Any, **kwargs: Any) -> str:
            return "점수: not_a_number\n최고: 1"

        client.generate = _generate  # type: ignore[method-assign, assignment]

        result = client.evaluate("question", ["a", "b"])
        # Falls back to length-based since no valid scores
        assert "길이 기반" in result["notes"]

    def test_evaluate_parse_best_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test evaluate handles malformed best line."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        _fake_genai(monkeypatch)

        client = gmc.GeminiModelClient()

        # Return valid scores but malformed best line
        def _generate(*args: Any, **kwargs: Any) -> str:
            return "점수: 3\n점수: 5\n최고: not_a_number"

        client.generate = _generate  # type: ignore[method-assign, assignment]

        result = client.evaluate("question", ["a", "bb"])
        # Should pick max score (index 1)
        assert result["best_index"] == 1
        assert result["scores"] == [3, 5]


class TestGeminiModelClientRewrite:
    """Test GeminiModelClient rewrite method."""

    def test_rewrite_generic_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rewrite handles generic exceptions."""
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        _fake_genai(monkeypatch)

        client = gmc.GeminiModelClient()

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("unexpected")

        client.generate = _raise  # type: ignore[method-assign, assignment]

        result = client.rewrite("original text")
        assert "재작성 실패(알 수 없음)" in result
