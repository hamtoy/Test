from __future__ import annotations

import pytest
import asyncio
import types
from pathlib import Path
import tempfile
from src import agent as ag
import google.generativeai.caching as caching


@pytest.mark.asyncio
async def test_agent_execute_api_call_safety_error(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.model_name = "tier-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    monkeypatch.setattr("src.agent.rate_limiter.DEFAULT_RPM_LIMIT", 1)
    monkeypatch.setattr("src.agent.rate_limiter.DEFAULT_RPM_WINDOW_SECONDS", 60)

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    agent._rate_limiter = None
    agent._semaphore = type(
        "Sem",
        (),
        {
            "__aenter__": lambda self: asyncio.sleep(0),
            "__aexit__": lambda self, exc_type, exc, tb: asyncio.sleep(0),
        },
    )()

    class _Resp:
        def __init__(self):
            self.candidates = [
                type(
                    "C",
                    (),
                    {"finish_reason": "BLOCK", "content": type("P", (), {"parts": []})},
                )()
            ]
            self.usage_metadata = None

    class _Model:
        async def generate_content_async(self, prompt_text, request_options=None):
            return _Resp()

    with pytest.raises(ag.SafetyFilterError):
        await agent._execute_api_call(_Model(), "prompt")


def test_agent_cache_budget_and_pricing(monkeypatch, tmp_path):
    # Minimal config stub
    class _Config:
        def __init__(self):
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.model_name = "tier-model"
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = 1.0

    # pricing tiers stub
    monkeypatch.setattr(
        "src.agent.cost_tracker.PRICING_TIERS",
        {"tier-model": [{"max_input_tokens": None, "input_rate": 1, "output_rate": 2}]},
    )
    monkeypatch.setattr("src.agent.rate_limiter.DEFAULT_RPM_LIMIT", 10)
    monkeypatch.setattr("src.agent.rate_limiter.DEFAULT_RPM_WINDOW_SECONDS", 60)

    # templates required (empty content)
    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)

    # cost calculations
    agent.total_input_tokens = 1_000_000
    agent.total_output_tokens = 1_000_000
    cost = agent.get_total_cost()
    assert cost == pytest.approx(3.0)
    assert agent.get_budget_usage_percent() == pytest.approx(300.0)

    # budget check raises
    with pytest.raises(ag.BudgetExceededError):
        agent.check_budget()


def test_agent_local_cache_load_and_store(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.model_name = "tier-model"
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    fp = "abc"
    # Avoid calling CachedContent.get in _load_local_cache
    monkeypatch.setattr(
        caching.CachedContent, "get", lambda name: types.SimpleNamespace(name=name)
    )
    agent._store_local_cache(fp, "name1", ttl_minutes=1)
    cached = agent._load_local_cache(fp, ttl_minutes=1)
    # _load_local_cache returns None unless CachedContent.get is patched; just ensure manifest exists and no crash
    assert (tmp_path / "cache" / "context_cache.json").exists()
    assert cached is not None


def test_agent_get_total_cost_invalid_model(monkeypatch):
    class _Config:
        def __init__(self):
            self.model_name = "unknown-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = Path(".")  # Dummy
            self.local_cache_dir = Path(".") / "cache"
            self.base_dir = Path(".")
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    tmp_path = Path(tempfile.mkdtemp(prefix="agent_cost_invalid_"))
    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    # Need to update config with temp path
    class _ConfigWithTemp:
        def __init__(self):
            self.model_name = "unknown-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    agent = ag.GeminiAgent(_ConfigWithTemp(), jinja_env=None)
    agent.total_input_tokens = 10
    agent.total_output_tokens = 10
    with pytest.raises(ValueError):
        agent.get_total_cost()


@pytest.mark.asyncio
async def test_agent_call_api_with_retry(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.model_name = "tier-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    agent._rate_limiter = None

    attempts = {"n": 0}

    async def _fake_exec(model, prompt_text):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise TimeoutError("retry me")
        return "ok"

    agent._execute_api_call = _fake_exec  # type: ignore[assignment]

    class _Sem:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    agent._semaphore = _Sem()

    class _Model:
        pass

    out = await agent._call_api_with_retry(_Model(), "p")
    assert out == "ok"
    assert attempts["n"] == 2
