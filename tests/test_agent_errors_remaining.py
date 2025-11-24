from __future__ import annotations

import types
from pathlib import Path

import pytest

from src.agent import GeminiAgent, CacheCreationError
from src.config import AppConfig

VALID_API_KEY = "AIza" + "F" * 35


def _agent(monkeypatch, tmp_path: Path):
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
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "prompt")
    )  # noqa: ARG005
    return GeminiAgent(AppConfig(), jinja_env=jinja_env)


def test_load_local_cache_bad_manifest(monkeypatch, tmp_path):
    agent = _agent(monkeypatch, tmp_path)
    manifest = agent._local_cache_manifest_path()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{broken", encoding="utf-8")
    assert agent._load_local_cache("fp", ttl_minutes=1) is None


@pytest.mark.asyncio
async def test_create_context_cache_raises(monkeypatch, tmp_path):
    agent = _agent(monkeypatch, tmp_path)

    class _Model:
        @staticmethod
        def count_tokens(content):
            return types.SimpleNamespace(total_tokens=9999)

    monkeypatch.setattr(
        type(agent),
        "_genai",
        property(
            lambda _self: types.SimpleNamespace(GenerativeModel=lambda name: _Model())
        ),
    )

    class _Caching:
        class CachedContent:
            @staticmethod
            def create(**kwargs):
                raise Exception("boom")

    monkeypatch.setattr(type(agent), "_caching", property(lambda _self: _Caching))

    with pytest.raises(CacheCreationError):
        await agent.create_context_cache("text")


def test_cost_error_unknown_model(monkeypatch, tmp_path):
    agent = _agent(monkeypatch, tmp_path)
    agent.config.model_name = "unknown-model"  # type: ignore[assignment]
    agent.total_input_tokens = 1000
    agent.total_output_tokens = 10
    with pytest.raises(ValueError):
        agent.get_total_cost()
