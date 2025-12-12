"""Tests for ActionExecutor."""

from __future__ import annotations

from typing import Any

import pytest

from src.features.action_executor import ActionExecutor


@pytest.mark.asyncio
async def test_execute_action_validate_branch() -> None:
    executor = ActionExecutor()
    result = await executor.execute_action(
        action="validate_quality",
        text="hello",
        max_length=3,
    )
    assert result["type"].startswith("validate")
    assert result["text"] == "hel"
    assert result["quality_score"] == 0.7


@pytest.mark.asyncio
async def test_execute_action_clean_branch() -> None:
    executor = ActionExecutor()
    result = await executor.execute_action(action="clean", text=" a  b ", max_length=10)
    assert result == "a b"


@pytest.mark.asyncio
async def test_execute_action_llm_provider_success() -> None:
    class _Resp:
        content = "llm"
        usage = {"tokens": 1}

    class _LLM:
        async def generate_content_async(self, **_kwargs: Any) -> _Resp:
            return _Resp()

    executor = ActionExecutor(llm_provider=_LLM())
    result = await executor.execute_action(
        action="summarize",
        text="hello",
        max_length=10,
        use_llm=True,
    )
    assert result == "llm"
    assert executor.last_llm_usage == {"tokens": 1}


@pytest.mark.asyncio
async def test_execute_action_llm_fallback_on_error() -> None:
    class _BadLLM:
        async def generate_content_async(self, **_kwargs: Any) -> Any:
            raise RuntimeError("boom")

    executor = ActionExecutor(llm_provider=_BadLLM())
    result = await executor.execute_action(
        action="summarize",
        text="hello",
        max_length=20,
        use_llm=True,
    )
    assert result.startswith("summarize:")
