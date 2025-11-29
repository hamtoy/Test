from __future__ import annotations

import pytest
import types
from typing import Any


import src.llm.gemini as gmc


def _fake_genai(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeModel:
        def __init__(self, name: str) -> None:
            self.name = name

        def generate_content(
            self, prompt: str, generation_config: Any = None
        ) -> types.SimpleNamespace:
            return types.SimpleNamespace(text="dummy")

    fake = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(name),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake)


def test_evaluate_parses_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()

    def fake_generate(prompt: str, role: str = "evaluator") -> str:
        return "점수1: 2\n점수2: 4\n점수3: 1\n최고: 2"

    client.generate = fake_generate  # type: ignore[method-assign, assignment]

    result = client.evaluate("q", ["a", "bb", "ccc"])
    assert result["best_index"] == 1
    assert result["scores"] == [2, 4, 1]
    assert result["notes"].startswith("점수 파싱")


def test_evaluate_api_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()

    def _raise(prompt: str, role: str = "evaluator") -> None:
        raise gmc.google_exceptions.GoogleAPIError("boom")  # type: ignore[attr-defined]

    client.generate = _raise  # type: ignore[method-assign, assignment]
    result = client.evaluate("q", ["a", "bbbb"])
    assert result["best_index"] == 1  # length-based fallback
    assert "길이 기반" in result["notes"]


def test_rewrite_handles_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()

    def _raise(prompt: str, role: str = "rewriter") -> None:
        raise gmc.google_exceptions.GoogleAPIError("rewrite error")  # type: ignore[attr-defined]

    client.generate = _raise  # type: ignore[method-assign, assignment]
    out = client.rewrite("text")
    assert "재작성 실패" in out
