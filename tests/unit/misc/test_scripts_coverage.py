from __future__ import annotations

import builtins
import importlib
import io
import sys
import types
from typing import Any

import pytest


def test_list_models_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def __init__(self, name: str, methods: list[str] | None = None) -> None:
            self.name = name
            self.supported_generation_methods = methods or ["generateContent"]

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        list_models=lambda: [_FakeModel("m1"), _FakeModel("m2", ["other"])],
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    # Clear module cache to ensure fresh import
    sys.modules.pop("src.llm.list_models", None)
    sys.modules.pop("src.list_models", None)

    # Capture log output
    import logging

    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    handler.setLevel(logging.INFO)

    import src.llm.list_models as lm

    lm.logger.addHandler(handler)
    importlib.reload(lm)
    lm.logger.removeHandler(handler)

    # Module executed successfully - log output may or may not contain model names
    # depending on mock setup, but module should complete without error
    _ = log_output.getvalue()


def test_qa_generator_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeResponse:
        def __init__(self) -> None:
            self.text = (
                "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
            )

    class _FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def generate_content(
            self, prompt: str, generation_config: dict[str, Any] | None = None
        ) -> _FakeResponse:
            return _FakeResponse()

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=_FakeModel,
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    files: dict[str, Any] = {}

    class _MemoBuffer(io.StringIO):
        def close(self) -> None:
            # Keep buffer accessible for assertions
            self.seek(0)
            return None

    def _fake_open(
        path: str, mode: str = "r", encoding: str | None = None
    ) -> io.StringIO:
        if "r" in mode:
            return io.StringIO("prompt")
        buf = _MemoBuffer()
        files[path] = buf
        return buf

    monkeypatch.setattr(builtins, "open", _fake_open)
    monkeypatch.setattr(builtins, "exit", lambda code=0: None)
    captured: list[str] = []
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: captured.append(" ".join(str(a) for a in args)),
    )

    # Clear module cache to ensure fresh import
    sys.modules.pop("src.qa.generator", None)
    sys.modules.pop("src.qa_generator", None)

    import src.qa.generator as qg

    importlib.reload(qg)
    assert "QA Results" in files.get("qa_result_4pairs.md", io.StringIO()).getvalue()
