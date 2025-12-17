"""Context and cache manager for GeminiAgent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from google.genai import types  # type: ignore[import-untyped]

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
        self,
        fingerprint: str,
        ttl_minutes: int,
        caching_module: Any,
    ) -> Any:
        """Load cached content manifest if available."""
        # Note: caching_module argument is kept for compatibility but might need refactoring
        # In google-genai, we retrieve by name directly from client.caches.get()

        # This delegates to cache_manager which deals with local JSON storage
        # We might need to slightly adapt cache_manager later if it does strict type checking
        return self.agent._cache_manager.load_local_cache(  # noqa: SLF001
            fingerprint,
            ttl_minutes,
            caching_module,  # This will be client.caches in the new setup
        )

    def store_local_cache(
        self,
        fingerprint: str,
        cache_name: str,
        ttl_minutes: int,
    ) -> None:
        """Persist cache manifest locally."""
        self.agent._cache_manager.store_local_cache(  # noqa: SLF001
            fingerprint,
            cache_name,
            ttl_minutes,
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
            self.agent.config,
            "cache_min_tokens",
            MIN_CACHE_TOKENS,
        )

        # Try to load existing cache from local manifest
        local_cached = self.load_local_cache(
            fingerprint,
            ttl_minutes,
            self.agent._caching,  # This returns client.caches
        )
        if local_cached:
            self.agent.logger.info(
                "Reusing context cache from disk: %s",
                local_cached.name,
            )
            return local_cached

        # Count tokens (async logic)
        token_count = 0
        try:
            # google-genai async count_tokens
            resp = await self.agent._genai_client.aio.models.count_tokens(
                model=self.agent.config.model_name, contents=combined_content
            )
            token_count = resp.total_tokens
        except Exception as e:
            self.agent.logger.warning("Failed to count tokens: %s", e)
            # Proceed anyway or fallback? Let's assume we proceed if we can't count
            pass

        self.agent.logger.info("Total Tokens for Caching: %s", token_count)

        if token_count > 0 and token_count < token_threshold:
            self.agent.logger.info(
                "Skipping cache creation (Tokens < %s)",
                token_threshold,
            )
            return None

        try:
            # Create cache using google-genai SDK
            # client.caches.create returns a CachedContent object

            # Note: client.caches.create is synchronous in current SDK wrapper usually?
            # Or is it async? The SDK documentation says client.aio.caches.create for async.

            # Let's use the async interface
            cache_config = types.CreateCachedContentConfig(
                model=self.agent.config.model_name,
                display_name="ocr_context_cache",
                system_instruction=system_prompt,
                contents=[ocr_text],
                ttl=f"{ttl_minutes * 60}s",  # TTL in "300s" format
            )

            # client.aio.caches.create uses config object
            cache = await self.agent._genai_client.aio.caches.create(
                config=cache_config
            )

            self.agent.logger.info(
                "Context Cache Created: %s (Expires in %sm)",
                cache.name,
                ttl_minutes,
            )
            try:
                self.store_local_cache(fingerprint, cache.name, ttl_minutes)
            except OSError as e:
                self.agent.logger.debug("Local cache manifest write skipped: %s", e)
            return cache

        except Exception as e:
            # Check for Rate Limit or other specific errors if possible
            if "ResourceExhausted" in str(e) or "429" in str(e):
                self.agent.logger.error(
                    "Failed to create cache due to rate limit: %s", e
                )
            else:
                self.agent.logger.error("Failed to create cache: %s", e)
            raise
