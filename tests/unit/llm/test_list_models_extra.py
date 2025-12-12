"""Extra tests for the list_models script module."""

from __future__ import annotations

import importlib
import sys
import types

import pytest


def test_list_models_exits_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    sys.modules.pop("src.llm.list_models", None)
    sys.modules.pop("src.list_models", None)
    with pytest.raises(SystemExit):
        importlib.import_module("src.llm.list_models")


def test_list_models_logs_supported_models(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Model:
        def __init__(self, name: str, methods: list[str]) -> None:
            self.name = name
            self.supported_generation_methods = methods

    import google.generativeai as genai

    monkeypatch.setattr(
        genai,
        "list_models",
        lambda: [
            _Model("m1", ["generateContent"]),
            _Model("m2", []),
        ],
    )
    monkeypatch.setattr(genai, "configure", lambda api_key: None)

    caplog.set_level("INFO")
    sys.modules.pop("src.llm.list_models", None)
    sys.modules.pop("src.list_models", None)
    importlib.import_module("src.llm.list_models")
    assert any("m1" in rec.message for rec in caplog.records)
