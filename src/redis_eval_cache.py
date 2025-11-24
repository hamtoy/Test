from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RedisEvalCache:
    """
    Redis-backed evaluation cache with TTL and fallback to in-memory dict.

    Persists LATS evaluation scores across worker restarts.
    """

    def __init__(self, redis_client: Optional[Any] = None, ttl: int = 3600):
        """
        Initialize Redis cache with fallback.

        Args:
            redis_client: Async Redis client instance (optional)
            ttl: Time-to-live for cache entries in seconds (default: 1 hour)
        """
        self.redis = redis_client
        self.prefix = "lats:eval:"
        self.ttl = ttl

        # Fallback to in-memory dict if Redis unavailable
        self.memory_cache: Dict[str, float] = {}
        self.use_redis = redis_client is not None

        if not self.use_redis:
            logger.warning(
                "Redis not available, using in-memory eval cache (no persistence)"
            )

    async def get(self, key: str) -> Optional[float]:
        """
        Retrieve cached evaluation score.

        Args:
            key: Cache key (typically state hash)

        Returns:
            Cached score or None if not found
        """
        try:
            if self.use_redis and self.redis:
                val = await self.redis.get(f"{self.prefix}{key}")
                if val is not None:
                    return float(val)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.warning(f"Redis cache get failed: {e}, falling back to memory")
            return self.memory_cache.get(key)

        return None

    async def set(self, key: str, score: float) -> None:
        """
        Store evaluation score in cache.

        Args:
            key: Cache key
            score: Evaluation score to cache
        """
        try:
            if self.use_redis and self.redis:
                await self.redis.setex(f"{self.prefix}{key}", self.ttl, str(score))
            # Always store in memory as backup
            self.memory_cache[key] = score
        except Exception as e:
            logger.warning(f"Redis cache set failed: {e}, stored in memory only")
            self.memory_cache[key] = score

    async def clear(self) -> None:
        """Clear all cached entries."""
        try:
            if self.use_redis and self.redis:
                # Delete all keys with our prefix
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(
                        cursor, match=f"{self.prefix}*", count=100
                    )
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
        except Exception as e:
            logger.warning(f"Redis cache clear failed: {e}")

        self.memory_cache.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "memory_entries": len(self.memory_cache),
            "using_redis": int(self.use_redis),
        }
