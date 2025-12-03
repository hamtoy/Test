"""Retry/backoff handler for GeminiAgent (stub for upcoming split)."""

from __future__ import annotations

from typing import Any

from src.agent import GeminiAgent


class RetryHandler:
    """Placeholder retry handler to allow gradual extraction from core."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    async def call(self, model: Any, prompt: str) -> str:
        """Delegate to agent's internal retry-capable call."""
        return await self.agent._call_api_with_retry(  # noqa: SLF001
            model, prompt
        )
