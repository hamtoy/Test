"""Gemini API client wrapper (stub for upcoming core split)."""

from __future__ import annotations

from typing import Any

from src.agent import GeminiAgent


class GeminiClient:
    """Thin wrapper facade for Gemini API calls.

    This stub preserves future extension points for request/response handling,
    retries, and telemetry without altering current behaviour.
    """

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    async def call_with_retry(self, model: Any, user_prompt: str) -> str:
        """Delegate to existing agent retry logic."""
        return await self.agent._call_api_with_retry(  # noqa: SLF001
            model, user_prompt
        )
