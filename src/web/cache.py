"""Answer caching system for QA generation performance optimization.

PHASE 2B: Caching system with Redis backend support.
- Redis available: Redis + memory (backup)
- Redis unavailable: Memory only (graceful fallback)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from src.config.constants import DEFAULT_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class AnswerCache:
    """Cache for generated QA answers with optional Redis backend.

    PHASE 2B: Hybrid cache supporting Redis persistence and in-memory fallback.
    Expected improvement: ~6-12s reduction on cache hits.

    Features:
    - SHA-256-based cache keys from (query, ocr_text, query_type)
    - TTL-based expiration (default 4 hours)
    - Redis persistence (optional) with memory backup
    - Graceful fallback on Redis errors
    - Cache hit/miss metrics logging
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        redis_client: Any | None = None,
    ) -> None:
        """Initialize the answer cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: from constants)
            redis_client: Optional async Redis client for persistence
        """
        self.cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        self.redis = redis_client
        self.use_redis = redis_client is not None
        self.prefix = "qa:answer:"

        if self.use_redis:
            logger.info(
                "AnswerCache initialized with Redis backend (TTL: %ds)", ttl_seconds
            )
        else:
            logger.info("AnswerCache initialized (in-memory, TTL: %ds)", ttl_seconds)

    def _make_key(self, query: str, ocr_text: str, query_type: str) -> str:
        """Generate cache key from inputs.

        Args:
            query: The query string
            ocr_text: OCR text content
            query_type: Type of query (e.g., 'explanation', 'reasoning')

        Returns:
            SHA-256 hash as cache key (secure and collision-resistant)
        """
        combined = f"{query}|{ocr_text}|{query_type}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def get(self, query: str, ocr_text: str, query_type: str) -> Any | None:
        """Retrieve cached answer if available and not expired.

        Args:
            query: The query string
            ocr_text: OCR text content
            query_type: Type of query

        Returns:
            Cached result or None if not found/expired
        """
        key = self._make_key(query, ocr_text, query_type)

        # Try Redis first if available
        if self.use_redis and self.redis:
            try:
                redis_key = f"{self.prefix}{key}"
                val = await self.redis.get(redis_key)
                if val is not None:
                    self._hits += 1
                    logger.info(
                        "Cache HIT (Redis): query_type=%s (saved ~6-12s)",
                        query_type,
                    )
                    return json.loads(val)
            except Exception as e:
                logger.warning("Redis cache get failed: %s, falling back to memory", e)

        # Fallback to memory cache
        if key in self.cache:
            value, timestamp = self.cache[key]
            age = time.monotonic() - timestamp
            if age < self.ttl:
                self._hits += 1
                logger.info(
                    "Cache HIT (memory): query_type=%s, age=%.1fs (saved ~6-12s)",
                    query_type,
                    age,
                )
                return value
            # Expired - remove it
            del self.cache[key]
            logger.debug(
                "Cache entry expired: query_type=%s, age=%.1fs",
                query_type,
                age,
            )

        self._misses += 1
        logger.debug("Cache MISS: query_type=%s", query_type)
        return None

    async def set(
        self, query: str, ocr_text: str, query_type: str, result: Any
    ) -> None:
        """Store result in cache.

        Args:
            query: The query string
            ocr_text: OCR text content
            query_type: Type of query
            result: The result to cache
        """
        key = self._make_key(query, ocr_text, query_type)

        # Store in Redis if available
        if self.use_redis and self.redis:
            try:
                redis_key = f"{self.prefix}{key}"
                await self.redis.setex(redis_key, self.ttl, json.dumps(result))
                logger.debug("Cache SET (Redis): query_type=%s", query_type)
            except Exception as e:
                logger.warning("Redis cache set failed: %s, stored in memory only", e)

        # Always store in memory as backup
        self.cache[key] = (result, time.monotonic())
        logger.debug(
            "Cache SET (memory): query_type=%s, cache_size=%d",
            query_type,
            len(self.cache),
        )

    def clear_expired(self) -> int:
        """Remove expired entries from memory cache.

        Returns:
            Number of entries removed
        """
        now = time.monotonic()
        expired = [k for k, (_, ts) in self.cache.items() if now - ts > self.ttl]
        for k in expired:
            del self.cache[k]

        if expired:
            logger.info("Cleared %d expired cache entries", len(expired))
        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate_percent": hit_rate,
            "cache_size": len(self.cache),
            "ttl_seconds": self.ttl,
            "using_redis": self.use_redis,
        }

    async def clear(self) -> None:
        """Clear all cache entries (memory and Redis)."""
        # Clear Redis keys if available
        if self.use_redis and self.redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor,
                        match=f"{self.prefix}*",
                        count=100,
                    )
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
                logger.info("Redis cache cleared")
            except Exception as e:
                logger.warning("Redis cache clear failed: %s", e)

        size = len(self.cache)
        self.cache.clear()
        logger.info("Memory cache cleared: %d entries removed", size)


# Global cache instance (singleton pattern)
# Uses DEFAULT_CACHE_TTL_SECONDS from constants (14400s = 4 hours)
# Redis client can be set later via answer_cache.redis = client
answer_cache = AnswerCache()
