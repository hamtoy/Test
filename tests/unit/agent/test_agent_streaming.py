"""Streaming support tests for GeminiAgent."""

import logging
from types import SimpleNamespace
from typing import Any, AsyncIterator, List

import pytest

from src.agent.core import GeminiAgent


class _DummyConfig:
    """Minimal config stub."""

    model_name = "gemini-1.5-pro"
    temperature = 0.2
    max_output_tokens = 128


class _FakeGenAI:
    """Fake genai module providing a streaming GenerativeModel."""

    class GenerativeModel:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        async def generate_content_async(
            self, prompt: str, stream: bool = False, **_: Any
        ) -> AsyncIterator[Any]:
            assert stream is True

            async def _gen() -> AsyncIterator[Any]:
                yield SimpleNamespace(text="hello ")
                yield SimpleNamespace(text="world")

            return _gen()


@pytest.mark.asyncio
async def test_generate_stream_yields_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = GeminiAgent.__new__(GeminiAgent)
    agent.config = _DummyConfig()
    agent.safety_settings = {}
    agent.logger = logging.getLogger("test")

    monkeypatch.setattr(GeminiAgent, "_genai", property(lambda self: _FakeGenAI()))

    chunks: List[str] = [part async for part in agent.generate_stream("prompt")]
    assert chunks == ["hello ", "world"]


@pytest.mark.asyncio
async def test_generate_stream_handles_empty_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyModel(_FakeGenAI.GenerativeModel):
        async def generate_content_async(
            self, prompt: str, stream: bool = False, **_: Any
        ) -> AsyncIterator[Any]:
            async def _gen() -> AsyncIterator[Any]:
                yield SimpleNamespace(text="")

            return _gen()

    class _FakeGenAIMixed(_FakeGenAI):
        GenerativeModel = _EmptyModel

    agent = GeminiAgent.__new__(GeminiAgent)
    agent.config = _DummyConfig()
    agent.safety_settings = {}
    agent.logger = logging.getLogger("test")
    monkeypatch.setattr(GeminiAgent, "_genai", property(lambda self: _FakeGenAIMixed()))

    chunks = [chunk async for chunk in agent.generate_stream("prompt")]
    assert chunks == []
