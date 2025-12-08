"""Context and cache manager for GeminiAgent."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any

from src.config.constants import MIN_CACHE_TOKENS

if TYPE_CHECKING:
    from src.agent import GeminiAgent


class AgentContextManager:
    """Wrapper around GeminiAgent cache/budget helpers."""

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the context manager wrapper."""
        self.agent = agent

    def track_cache_usage(self, hit: bool) -> None:
        """Proxy cache usage tracking."""
        self.agent._cache_manager.track_cache_usage(hit)  # noqa: SLF001

    def get_cached_content(self, cache_key: str) -> str | None:
        """Proxy cache fetch."""
        return (
            self.agent._cache.get(cache_key) if hasattr(self.agent, "_cache") else None
        )

    def cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """Remove expired cache entries."""
        self.agent._cache_manager.cleanup_expired_cache(ttl_minutes)  # noqa: SLF001

    def load_local_cache(
        self, fingerprint: str, ttl_minutes: int, caching_module: Any,
    ) -> Any:
        """Load cached content manifest if available."""
        return self.agent._cache_manager.load_local_cache(  # noqa: SLF001
            fingerprint, ttl_minutes, caching_module,
        )

    def store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int,
    ) -> None:
        """Persist cache manifest locally."""
        self.agent._cache_manager.store_local_cache(  # noqa: SLF001
            fingerprint, cache_name, ttl_minutes,
        )

    async def create_context_cache(self, ocr_text: str) -> Any:
        """Create a Gemini Context Cache based on OCR text."""
        system_prompt = self.agent.jinja_env.get_template("system/eval.j2").render()
        combined_content = system_prompt + "\n\n" + ocr_text
        fingerprint = self.agent._cache_manager.compute_fingerprint(  # noqa: SLF001
            combined_content,
        )
        ttl_minutes = self.agent.config.cache_ttl_minutes
        token_threshold = getattr(
            self.agent.config, "cache_min_tokens", MIN_CACHE_TOKENS,
        )

        local_cached = self.load_local_cache(
            fingerprint,
            ttl_minutes,
            self.agent._caching,  # noqa: SLF001
        )
        if local_cached:
            self.agent.logger.info(
                "Reusing context cache from disk: %s", local_cached.name,
            )
            return local_cached

        loop = asyncio.get_running_loop()

        def _count_tokens() -> int:
            model = self.agent._genai.GenerativeModel(  # noqa: SLF001
                self.agent.config.model_name,
            )
            result: int = model.count_tokens(combined_content).total_tokens
            return result

        token_count = await loop.run_in_executor(None, _count_tokens)
        self.agent.logger.info("Total Tokens for Caching: %s", token_count)

        if token_count < token_threshold:
            self.agent.logger.info(
                "Skipping cache creation (Tokens < %s)", token_threshold,
            )
            return None

        try:

            def _create_cache() -> Any:
                return self.agent._caching.CachedContent.create(  # noqa: SLF001
                    model=self.agent.config.model_name,
                    display_name="ocr_context_cache",
                    system_instruction=system_prompt,
                    contents=[ocr_text],
                    ttl=datetime.timedelta(minutes=ttl_minutes),
                )

            cache = await loop.run_in_executor(None, _create_cache)
            self.agent.logger.info(
                "Context Cache Created: %s (Expires in %sm)", cache.name, ttl_minutes,
            )
            try:
                self.store_local_cache(fingerprint, cache.name, ttl_minutes)
            except OSError as e:
                self.agent.logger.debug("Local cache manifest write skipped: %s", e)
            return cache
        except self.agent._google_exceptions().ResourceExhausted as e:  # noqa: SLF001
            self.agent.logger.error("Failed to create cache due to rate limit: %s", e)
            raise
        except (ValueError, RuntimeError, OSError) as e:
            self.agent.logger.error("Failed to create cache: %s", e)
            raise
