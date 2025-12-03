from __future__ import annotations

import types
from pathlib import Path
from typing import Any

import pytest
from jinja2 import DictLoader, Environment

from src.agent import GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "E" * 35


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "GEMINI_API_KEY": VALID_API_KEY,
            "GEMINI_MODEL_NAME": "gemini-flash-latest",
            "GEMINI_MAX_OUTPUT_TOKENS": 1024,
            "GEMINI_TIMEOUT": 60,
            "GEMINI_MAX_CONCURRENCY": 2,
            "GEMINI_CACHE_SIZE": 10,
            "GEMINI_TEMPERATURE": 0.2,
            "GEMINI_CACHE_TTL_MINUTES": 5,
            "LOG_LEVEL": "INFO",
            "CACHE_STATS_FILE": "cache_stats.jsonl",
            "CACHE_STATS_MAX_ENTRIES": 100,
            "LOCAL_CACHE_DIR": str(tmp_path / ".cache"),
            "BUDGET_LIMIT_USD": 100,
        }
    )


def _make_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> GeminiAgent:
    config = _make_config(tmp_path)
    jinja_env = Environment(loader=DictLoader({"system/eval.j2": "x"}))
    agent = GeminiAgent(config, jinja_env=jinja_env)

    # Avoid touching real genai client, provide protos stub
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
async def test_execute_api_call_logs_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _make_agent(monkeypatch, tmp_path)
    logged: dict[str, Any] = {}

    def _log_metrics(logger: Any, **kwargs: Any) -> None:
        logged.update(kwargs)

    # Patch src.agent.log_metrics so _get_log_metrics() finds it
    import src.agent as agent_mod

    monkeypatch.setattr(agent_mod, "log_metrics", _log_metrics)
    # Agent/Client가 이미 생성된 후이므로 직접 덮어쓴다.
    agent._log_metrics = _log_metrics
    agent.client._log_metrics = _log_metrics

    class _Resp:
        def __init__(self) -> None:
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
        async def generate_content_async(
            prompt_text: str, request_options: Any = None
        ) -> _Resp:  # noqa: ARG002
            return _Resp()

    result = await agent._execute_api_call(_Model(), "p")
    assert result == "ok"
    assert logged["prompt_tokens"] == 10
    assert logged["completion_tokens"] == 5
    assert "latency_ms" in logged


def test_get_total_cost_unknown_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _make_agent(monkeypatch, tmp_path)
    agent._cost_tracker.model_name = "unknown-model"
    agent.total_input_tokens = 10
    agent.total_output_tokens = 5
    with pytest.raises(ValueError):
        agent.get_total_cost()
