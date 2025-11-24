from __future__ import annotations

import logging
from pathlib import Path

import pytest
from jinja2 import DictLoader, Environment

from src.agent import BudgetExceededError, GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "D" * 35


def _config(tmp_path: Path, budget: float) -> AppConfig:
    return AppConfig.model_validate(
        {
            "GEMINI_API_KEY": VALID_API_KEY,
            "GEMINI_MODEL_NAME": "gemini-3-pro-preview",
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
            "BUDGET_LIMIT_USD": budget,
        }
    )


def _agent_with_budget(
    spent_input_tokens: int, spent_output_tokens: int, budget: float, tmp_path: Path
) -> GeminiAgent:
    config = _config(tmp_path, budget)
    jinja_env = Environment(loader=DictLoader({"prompt_eval.j2": "x"}))
    agent = GeminiAgent(config, jinja_env=jinja_env)
    agent.total_input_tokens = spent_input_tokens
    agent.total_output_tokens = spent_output_tokens
    return agent


def test_budget_warning_logs(caplog, tmp_path):
    agent = _agent_with_budget(
        200_000, 0, budget=0.01, tmp_path=tmp_path
    )  # forces high pct
    with caplog.at_level(logging.WARNING), pytest.raises(BudgetExceededError):
        agent.check_budget()
    assert any("Budget nearing limit" in rec.message for rec in caplog.records)


def test_budget_ok(tmp_path):
    agent = _agent_with_budget(1_000, 1_000, budget=1000.0, tmp_path=tmp_path)
    agent.check_budget()  # should not raise
