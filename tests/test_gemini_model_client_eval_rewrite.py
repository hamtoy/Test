import types


import src.gemini_model_client as gmc


def _fake_genai(monkeypatch):
    class _FakeModel:
        def __init__(self, name: str):
            self.name = name

        def generate_content(self, prompt, generation_config=None):
            return types.SimpleNamespace(text="dummy")

    fake = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(name),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake)


def test_evaluate_parses_scores(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()
    client.generate = (
        lambda prompt, role="evaluator": "점수1: 2\n점수2: 4\n점수3: 1\n최고: 2"
    )

    result = client.evaluate("q", ["a", "bb", "ccc"])
    assert result["best_index"] == 1
    assert result["scores"] == [2, 4, 1]
    assert result["notes"].startswith("점수 파싱")


def test_evaluate_api_error_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()

    def _raise(prompt, role="evaluator"):
        raise gmc.google_exceptions.GoogleAPIError("boom")

    client.generate = _raise
    result = client.evaluate("q", ["a", "bbbb"])
    assert result["best_index"] == 1  # length-based fallback
    assert "길이 기반" in result["notes"]


def test_rewrite_handles_api_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    _fake_genai(monkeypatch)

    client = gmc.GeminiModelClient()

    def _raise(prompt, role="rewriter"):
        raise gmc.google_exceptions.GoogleAPIError("rewrite error")

    client.generate = _raise
    out = client.rewrite("text")
    assert "재작성 실패" in out
