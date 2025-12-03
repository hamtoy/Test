"""Context and cache manager for GeminiAgent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.agent import GeminiAgent


class AgentContextManager:
    """Wrapper around GeminiAgent cache/budget helpers."""

    def __init__(self, agent: "GeminiAgent") -> None:
        self.agent = agent

    def track_cache_usage(self, hit: bool) -> None:
        """Proxy cache usage tracking."""
        self.agent._cache_manager.track_cache_usage(hit)  # noqa: SLF001

    def get_cached_content(self, cache_key: str) -> Optional[str]:
        """Proxy cache fetch."""
        return (
            self.agent._cache.get(cache_key) if hasattr(self.agent, "_cache") else None
        )

    def cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """Remove expired cache entries."""
        self.agent._cache_manager.cleanup_expired_cache(ttl_minutes)  # noqa: SLF001

    def load_local_cache(
        self, fingerprint: str, ttl_minutes: int, caching_module: Any
    ) -> Any:
        """Load cached content manifest if available."""
        return self.agent._cache_manager.load_local_cache(  # noqa: SLF001
            fingerprint, ttl_minutes, caching_module
        )

    def store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        """Persist cache manifest locally."""
        self.agent._cache_manager.store_local_cache(  # noqa: SLF001
            fingerprint, cache_name, ttl_minutes
        )
