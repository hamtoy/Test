from __future__ import annotations

import types
from typing import Any
from unittest.mock import AsyncMock

import pytest
from jinja2 import DictLoader, Environment

from src.agent import GeminiAgent
from src.config.exceptions import SafetyFilterError
from src.config import AppConfig

VALID_API_KEY = "AIza" + "B" * 35


def _dummy_env() -> Environment:
    return Environment(
        loader=DictLoader(
            {
                "prompt_eval.j2": "system-eval",
                "prompt_rewrite.j2": "system-rewrite",
                "rewrite_user.j2": "{{ best_answer }}",
                "prompt_query_gen.j2": "query-gen",
                "query_gen_user.j2": "user-gen",
            }
        )
    )


def _make_agent(monkeypatch: pytest.MonkeyPatch) -> GeminiAgent:
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.delenv("BUDGET_LIMIT_USD", raising=False)
    stub_genai = types.SimpleNamespace(
        GenerativeModel=lambda *args, **kwargs: types.SimpleNamespace()
    )
    monkeypatch.setattr(GeminiAgent, "_genai", property(lambda _self: stub_genai))
    return GeminiAgent(AppConfig(), jinja_env=_dummy_env())


def _patch_protos(monkeypatch: pytest.MonkeyPatch) -> None:
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


@pytest.mark.asyncio
async def test_execute_api_call_blocks_on_safety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_protos(monkeypatch)
    agent = _make_agent(monkeypatch)

    class _Resp:
        def __init__(self) -> None:
            self.candidates = [types.SimpleNamespace(finish_reason="BLOCK")]
            self.prompt_feedback = "PF"
            self.usage_metadata = None

    class _Model:
        @staticmethod
        async def generate_content_async(
            prompt_text: str, request_options: Any = None
        ) -> _Resp:  # noqa: ARG002
            return _Resp()

    with pytest.raises(SafetyFilterError):
        await agent._execute_api_call(_Model(), "p")


@pytest.mark.asyncio
async def test_execute_api_call_fallbacks_to_candidate_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_protos(monkeypatch)
    agent = _make_agent(monkeypatch)

    class _Part:
        def __init__(self) -> None:
            self.text = "fallback-text"

    class _Content:
        parts = [_Part()]

    class _Resp:
        def __init__(self) -> None:
            self.candidates = [
                types.SimpleNamespace(finish_reason="STOP", content=_Content())
            ]
            self.prompt_feedback = "PF"
            self.usage_metadata = types.SimpleNamespace(
                prompt_token_count=1, candidates_token_count=2, total_token_count=3
            )

        @property
        def text(self) -> None:
            raise ValueError("no text")

    class _Model:
        @staticmethod
        async def generate_content_async(
            prompt_text: str, request_options: Any = None
        ) -> _Resp:  # noqa: ARG002
            return _Resp()

    result = await agent._execute_api_call(_Model(), "p")
    assert result == "fallback-text"


@pytest.mark.asyncio
async def test_generate_query_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(agent, "_call_api_with_retry", AsyncMock(return_value="   "))
    result = await agent.generate_query("ocr", "user prompt")
    assert result == []


@pytest.mark.asyncio
async def test_evaluate_responses_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(agent, "_call_api_with_retry", AsyncMock(return_value=" "))
    with pytest.raises(ValueError):
        await agent.evaluate_responses("ocr", "q", {"a": "b"})


@pytest.mark.asyncio
async def test_rewrite_best_answer_unwraps(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _make_agent(monkeypatch)
    monkeypatch.setattr(
        agent,
        "_call_api_with_retry",
        AsyncMock(return_value='{"rewritten_answer":"ok"}'),
    )
    rewritten = await agent.rewrite_best_answer("ctx", "best")
    assert rewritten == "ok"
