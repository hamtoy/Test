from __future__ import annotations

import types

import src.gemini_model_client as gmc


def test_generate_logs_metrics(monkeypatch):
    captured = {}

    def _log_metrics(logger, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("src.gemini_model_client.log_metrics", _log_metrics)
    monkeypatch.setattr(gmc, "require_env", lambda name: "key")

    class _Usage:
        prompt_token_count = 10
        candidates_token_count = 5

    class _Resp:
        def __init__(self):
            self.text = "ok"
            self.usage_metadata = _Usage()

    class _Model:
        def generate_content(self, prompt, generation_config=None):  # noqa: ARG002
            return _Resp()

    client = gmc.GeminiModelClient.__new__(gmc.GeminiModelClient)
    client.model_name = "gemini-3-pro-preview"
    client.model = _Model()
    client.logger = types.SimpleNamespace(info=lambda *a, **k: None)

    out = client.generate("hi")
    assert out == "ok"
    assert captured["prompt_tokens"] == 10
    assert captured["completion_tokens"] == 5


def test_evaluate_and_rewrite_log_metrics(monkeypatch):
    captured = []

    def _log_metrics(logger, **kwargs):
        captured.append(kwargs)

    monkeypatch.setattr("src.gemini_model_client.log_metrics", _log_metrics)
    monkeypatch.setattr(gmc, "require_env", lambda name: "key")

    class _Usage:
        prompt_token_count = 1
        candidates_token_count = 1

    class _Resp:
        def __init__(self, text):
            self.text = text
            self.usage_metadata = _Usage()

    class _Model:
        def __init__(self):
            self.calls = 0

        def generate_content(self, prompt, generation_config=None):  # noqa: ARG002
            self.calls += 1
            if self.calls == 1:
                return _Resp("점수1: 1\n점수2: 2\n최고: 2")
            return _Resp("rewritten")

    client = gmc.GeminiModelClient.__new__(gmc.GeminiModelClient)
    client.model_name = "gemini-3-pro-preview"
    client.model = _Model()
    client.logger = types.SimpleNamespace(info=lambda *a, **k: None)

    eval_res = client.evaluate("q", ["a", "bb"])
    rewritten = client.rewrite("answer")

    assert eval_res["best_index"] == 1
    assert rewritten == "rewritten"
    assert captured  # metrics logged at least once
