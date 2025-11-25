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
