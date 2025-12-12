"""Extra tests for src.llm.init_genai."""

from __future__ import annotations

import pytest

from src.llm import init_genai


def test_configure_genai_returns_false_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    init_genai._configured = False
    assert init_genai.configure_genai(api_key=None) is False


def test_configure_genai_sets_flag_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google.generativeai as genai

    calls: list[str] = []

    def _configure(api_key: str) -> None:
        calls.append(api_key)

    monkeypatch.setattr(genai, "configure", _configure)

    init_genai._configured = False
    assert init_genai.configure_genai(api_key="k1") is True
    assert calls == ["k1"]
    assert init_genai.is_configured() is True

    calls.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    assert init_genai.configure_genai() is True
    assert calls == []
