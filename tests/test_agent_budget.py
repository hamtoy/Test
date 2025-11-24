from __future__ import annotations

import logging
from pathlib import Path
import types

import pytest

from src.agent import GeminiAgent, BudgetExceededError
from src.config import AppConfig

VALID_API_KEY = "AIza" + "D" * 35


def _agent_with_budget(
    monkeypatch,
    spent_input_tokens: int,
    spent_output_tokens: int,
    budget: float,
    tmp_path: Path,
):
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
    monkeypatch.setenv("BUDGET_LIMIT_USD", str(budget))
    jinja_env = types.SimpleNamespace(
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "x")
    )  # noqa: ARG005
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)
    agent.total_input_tokens = spent_input_tokens
    agent.total_output_tokens = spent_output_tokens
    return agent


def test_budget_warning_logs(monkeypatch, caplog, tmp_path):
    agent = _agent_with_budget(
        monkeypatch, 200_000, 0, budget=0.01, tmp_path=tmp_path
    )  # forces high pct
    with caplog.at_level(logging.WARNING), pytest.raises(BudgetExceededError):
        agent.check_budget()
    assert any("Budget nearing limit" in rec.message for rec in caplog.records)


def test_budget_ok(monkeypatch, tmp_path):
    agent = _agent_with_budget(
        monkeypatch, 1_000, 1_000, budget=1000.0, tmp_path=tmp_path
    )
    agent.check_budget()  # should not raise
