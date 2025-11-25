from __future__ import annotations

import types
from src import gemini_model_client as gmc


def test_gemini_model_client_behaviors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    class _FakeGenConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _FakeModel:
        def __init__(self, _name):
            pass

        def generate_content(self, prompt, generation_config=None):
            return types.SimpleNamespace(text=f"LLM:{prompt[:10]}")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(name),
        types=types.SimpleNamespace(GenerationConfig=_FakeGenConfig),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)

    client = gmc.GeminiModelClient()
    assert client.generate("hello").startswith("LLM:")

    empty_eval = client.evaluate("q", [])
    assert empty_eval["best_answer"] is None

    length_eval = client.evaluate("q", ["a", "bb"])
    assert length_eval["best_index"] == 1

    client.generate = (
        lambda prompt, role="default": "점수1: 2\n점수2: 4\n점수3: 1\n최고: 2"
    )
    parsed_eval = client.evaluate("q", ["a", "bb", "ccc"])
    assert parsed_eval["best_index"] == 1

    client.generate = lambda prompt, role="rewriter": "rewritten text"
    assert client.rewrite("orig").startswith("rewritten")


def test_gemini_model_client_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeResponse:
        def __init__(self, text, usage=None, candidates=None):
            self.text = text
            self.usage_metadata = usage
            self.candidates = candidates

    class _FakeModel:
        def __init__(self):
            self.calls = []

        def generate_content(self, prompt, generation_config=None):
            self.calls.append(("gen", prompt))
            raise gmc.google_exceptions.GoogleAPIError("boom")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name="m": _FakeModel(),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)
    client = gmc.GeminiModelClient()

    # generate handles exceptions
    assert client.generate("hi").startswith("[생성 실패")

    # evaluate len-based fallback on parse failure
    client.generate = lambda prompt, role="evaluator": "not numbers"
    eval_res = client.evaluate("q", ["a", "bb", "ccc"])
    assert eval_res["best_index"] == 2

    # rewrite/fact_check exception paths
    client.generate = lambda prompt, role="rewriter": (_ for _ in ()).throw(
        gmc.google_exceptions.GoogleAPIError("rewriter error")
    )
    assert "재작성 실패" in client.rewrite("text")


def test_gemini_model_client_type_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def generate_content(self, *args, **kwargs):
            raise TypeError("bad")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)

    client = gmc.GeminiModelClient()
    assert "[생성 실패(입력 오류" in client.generate("prompt")
