from __future__ import annotations

import types
import sys
import importlib
import builtins
import io


def test_list_models_script(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def __init__(self, name, methods=None) -> None:
            self.name = name
            self.supported_generation_methods = methods or ["generateContent"]

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        list_models=lambda: [_FakeModel("m1"), _FakeModel("m2", ["other"])],
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    captured = []
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: captured.append(" ".join(str(a) for a in args)),
    )
    monkeypatch.setattr(
        builtins, "exit", lambda code=0: captured.append(f"exit:{code}")
    )

    # Clear module cache to ensure fresh import
    sys.modules.pop("src.llm.list_models", None)
    sys.modules.pop("src.list_models", None)

    import src.llm.list_models as lm

    importlib.reload(lm)
    assert captured


def test_qa_generator_script(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeCompletions:
        def create(self, model, messages, temperature=0):
            content = (
                "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
            )
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content=content)
                    )
                ]
            )

    class _FakeChat:
        def __init__(self) -> None:
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = _FakeChat()

    fake_openai_module = types.SimpleNamespace(OpenAI=_FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    files: dict[str, Any] = {}

    class _MemoBuffer(io.StringIO):
        def close(self):
            # Keep buffer accessible for assertions
            self.seek(0)
            return None

    def _fake_open(path, mode="r", encoding=None):
        if "r" in mode:
            return io.StringIO("prompt")
        buf = _MemoBuffer()
        files[path] = buf
        return buf

    monkeypatch.setattr(builtins, "open", _fake_open)
    monkeypatch.setattr(builtins, "exit", lambda code=0: None)
    captured = []
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
