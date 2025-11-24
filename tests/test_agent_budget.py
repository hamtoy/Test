from __future__ import annotations

import logging
import types

import pytest

from src.agent import GeminiAgent, BudgetExceededError
from src.config import AppConfig

VALID_API_KEY = "AIza" + "D" * 35


def _agent_with_budget(
    monkeypatch, spent_input_tokens: int, spent_output_tokens: int, budget: float
):
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("BUDGET_LIMIT_USD", str(budget))
    jinja_env = types.SimpleNamespace(
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "x")
    )  # noqa: ARG005
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)
    agent.total_input_tokens = spent_input_tokens
    agent.total_output_tokens = spent_output_tokens
    return agent


def test_budget_warning_logs(monkeypatch, caplog):
    agent = _agent_with_budget(monkeypatch, 200_000, 0, budget=0.01)  # forces high pct
    with caplog.at_level(logging.WARNING), pytest.raises(BudgetExceededError):
        agent.check_budget()
    assert any("Budget nearing limit" in rec.message for rec in caplog.records)


def test_budget_ok(monkeypatch):
    agent = _agent_with_budget(monkeypatch, 1_000, 1_000, budget=1000.0)
    agent.check_budget()  # should not raise
