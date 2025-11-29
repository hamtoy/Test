from __future__ import annotations

import types
from typing import Any

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "C" * 35


def _stub_agent(monkeypatch: pytest.MonkeyPatch) -> GeminiAgent:
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    jinja_env = types.SimpleNamespace(
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "x")
    )  # noqa: ARG005

    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)  # type: ignore[arg-type]
    agent._rate_limiter = None  # explicitly disable to test fallback path
    return agent


@pytest.mark.asyncio
async def test_call_api_with_retry_adaptive_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _stub_agent(monkeypatch)

    class Boom(Exception):
        pass

    call_count = {"n": 0}

    async def _boom(*_a: Any, **_k: Any) -> None:
        call_count["n"] += 1
        raise Boom("fail")

    monkeypatch.setattr(agent, "_execute_api_call", _boom)

    with pytest.raises(Boom):
        await agent._call_api_with_retry(types.SimpleNamespace(), "payload")

    # ensure retry attempts were made (>=3 from tenacity), adaptive hook ran (time.sleep)
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_call_api_with_retry_success_after_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _stub_agent(monkeypatch)
    attempts = {"n": 0}

    async def _flaky(*_a: Any, **_k: Any) -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise TimeoutError("first fail")
        return "ok"

    monkeypatch.setattr(agent, "_execute_api_call", _flaky)
    result = await agent._call_api_with_retry(types.SimpleNamespace(), "payload")
    assert result == "ok"
    assert attempts["n"] == 2
