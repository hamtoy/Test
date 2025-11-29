from __future__ import annotations

import types
from pathlib import Path
from typing import Any

import pytest

from jinja2 import DictLoader, Environment

from src.agent import GeminiAgent
from src.config.exceptions import CacheCreationError
from src.config import AppConfig

VALID_API_KEY = "AIza" + "F" * 35


def _agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> GeminiAgent:
    config = AppConfig.model_validate(
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
            "BUDGET_LIMIT_USD": 100,
        }
    )
    jinja_env = Environment(loader=DictLoader({"prompt_eval.j2": "prompt"}))
    return GeminiAgent(config, jinja_env=jinja_env)


def test_load_local_cache_bad_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _agent(monkeypatch, tmp_path)
    manifest = agent._local_cache_manifest_path()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{broken", encoding="utf-8")
    assert agent._load_local_cache("fp", ttl_minutes=1) is None


@pytest.mark.asyncio
async def test_create_context_cache_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _agent(monkeypatch, tmp_path)

    class _Model:
        @staticmethod
        def count_tokens(content: Any) -> types.SimpleNamespace:
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
            def create(**kwargs: Any) -> None:
                raise RuntimeError("boom")

    monkeypatch.setattr(type(agent), "_caching", property(lambda _self: _Caching))

    with pytest.raises(CacheCreationError):
        await agent.create_context_cache("text")


def test_cost_error_unknown_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = _agent(monkeypatch, tmp_path)
    agent._cost_tracker.model_name = "unknown-model"
    agent.total_input_tokens = 1000
    agent.total_output_tokens = 10
    with pytest.raises(ValueError):
        agent.get_total_cost()
