from __future__ import annotations

import types
from pathlib import Path

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "E" * 35


def _make_agent(monkeypatch, tmp_path: Path):
    # Provide all required settings via env
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")
    monkeypatch.setenv("GEMINI_MAX_OUTPUT_TOKENS", "1024")
    monkeypatch.setenv("GEMINI_TIMEOUT", "60")
    monkeypatch.setenv("GEMINI_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("GEMINI_CACHE_SIZE", "10")
    monkeypatch.setenv("GEMINI_TEMPERATURE", "0.2")
    monkeypatch.setenv("GEMINI_CACHE_TTL_MINUTES", "5")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("CACHE_STATS_FILE", "cache_stats.jsonl")
    monkeypatch.setenv("CACHE_STATS_MAX_ENTRIES", "100")
    monkeypatch.setenv("LOCAL_CACHE_DIR", str(tmp_path / ".cache"))
    monkeypatch.setenv("BUDGET_LIMIT_USD", "100")

    jinja_env = types.SimpleNamespace(
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "x")
    )  # noqa: ARG005
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)

    # Avoid touching real genai client
    class _Finish:
        STOP = "STOP"
        MAX_TOKENS = "MAX_TOKENS"

    class _Candidate:
        FinishReason = _Finish

    monkeypatch.setattr(
        GeminiAgent,
        "_protos",
        lambda _self: types.SimpleNamespace(Candidate=_Candidate),
    )
    return agent


@pytest.mark.asyncio
async def test_execute_api_call_logs_metrics(monkeypatch, tmp_path):
    agent = _make_agent(monkeypatch, tmp_path)
    logged = {}

    def _log_metrics(logger, **kwargs):
        logged.update(kwargs)

    monkeypatch.setattr("src.agent.log_metrics", _log_metrics)

    class _Resp:
        def __init__(self):
            self.candidates = [
                types.SimpleNamespace(finish_reason="STOP", content=None)
            ]
            self.prompt_feedback = None
            self.usage_metadata = types.SimpleNamespace(
                prompt_token_count=10, candidates_token_count=5, total_token_count=15
            )
            self.text = "ok"

    class _Model:
        @staticmethod
        async def generate_content_async(prompt_text, request_options=None):  # noqa: ARG002
            return _Resp()

    result = await agent._execute_api_call(_Model(), "p")
    assert result == "ok"
    assert logged["prompt_tokens"] == 10
    assert logged["completion_tokens"] == 5
    assert "latency_ms" in logged


def test_get_total_cost_unknown_model(monkeypatch, tmp_path):
    agent = _make_agent(monkeypatch, tmp_path)
    agent.config.model_name = "unknown-model"  # type: ignore[assignment]
    agent.total_input_tokens = 10
    agent.total_output_tokens = 5
    with pytest.raises(ValueError):
        agent.get_total_cost()
