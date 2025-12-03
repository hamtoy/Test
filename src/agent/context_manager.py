"""Context and cache manager for GeminiAgent (stub for upcoming split)."""

from __future__ import annotations

from typing import Optional

from src.agent import GeminiAgent


class AgentContextManager:
    """Placeholder wrapper around GeminiAgent cache/budget helpers."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    def track_cache_usage(self, hit: bool) -> None:
        """Proxy cache usage tracking."""
        self.agent._track_cache_usage(hit)  # noqa: SLF001

    def get_cached_content(self, cache_key: str) -> Optional[str]:
        """Proxy cache fetch."""
        return (
            self.agent._cache.get(cache_key) if hasattr(self.agent, "_cache") else None
        )
