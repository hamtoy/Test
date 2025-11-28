"""Tests for src/caching/redis_cache.py to improve coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestRedisEvalCacheNoRedis:
    """Test RedisEvalCache without Redis (in-memory mode)."""

    def test_init_without_redis(self):
        """Test initialization without Redis client."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None, ttl=3600)

        assert cache.redis is None
        assert cache.ttl == 3600
        assert cache.use_redis is False
        assert cache.prefix == "lats:eval:"
        assert cache.memory_cache == {}

    def test_init_with_redis(self):
        """Test initialization with Redis client."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = MagicMock()
        cache = RedisEvalCache(redis_client=mock_redis, ttl=7200)

        assert cache.redis is mock_redis
        assert cache.ttl == 7200
        assert cache.use_redis is True

    @pytest.mark.asyncio
    async def test_get_memory_only(self):
        """Test get from memory cache when Redis is not available."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None)
        cache.memory_cache["test_key"] = 0.95

        result = await cache.get("test_key")
        assert result == 0.95

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        """Test get returns None for missing key."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None)

        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_memory_only(self):
        """Test set to memory cache when Redis is not available."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None)

        await cache.set("test_key", 0.85)

        assert cache.memory_cache["test_key"] == 0.85

    @pytest.mark.asyncio
    async def test_clear_memory_only(self):
        """Test clear memory cache."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None)
        cache.memory_cache["key1"] = 0.5
        cache.memory_cache["key2"] = 0.6

        await cache.clear()

        assert cache.memory_cache == {}

    def test_get_stats(self):
        """Test get_stats returns correct stats."""
        from src.caching.redis_cache import RedisEvalCache

        cache = RedisEvalCache(redis_client=None)
        cache.memory_cache["key1"] = 0.5
        cache.memory_cache["key2"] = 0.6

        stats = cache.get_stats()

        assert stats["memory_entries"] == 2
        assert stats["using_redis"] == 0


class TestRedisEvalCacheWithRedis:
    """Test RedisEvalCache with Redis mock."""

    @pytest.mark.asyncio
    async def test_get_from_redis(self):
        """Test get retrieves from Redis."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="0.95")

        cache = RedisEvalCache(redis_client=mock_redis)

        result = await cache.get("test_key")

        assert result == 0.95
        mock_redis.get.assert_called_once_with("lats:eval:test_key")

    @pytest.mark.asyncio
    async def test_get_from_redis_returns_none(self):
        """Test get returns None when Redis has no value."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        cache = RedisEvalCache(redis_client=mock_redis)

        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_redis_error_fallback(self):
        """Test get falls back to memory on Redis error."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))

        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["test_key"] = 0.75

        result = await cache.get("test_key")

        assert result == 0.75

    @pytest.mark.asyncio
    async def test_set_to_redis(self):
        """Test set stores in Redis and memory."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        cache = RedisEvalCache(redis_client=mock_redis, ttl=3600)

        await cache.set("test_key", 0.85)

        mock_redis.setex.assert_called_once_with("lats:eval:test_key", 3600, "0.85")
        assert cache.memory_cache["test_key"] == 0.85

    @pytest.mark.asyncio
    async def test_set_redis_error_fallback(self):
        """Test set stores in memory only on Redis error."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis write error"))

        cache = RedisEvalCache(redis_client=mock_redis)

        await cache.set("test_key", 0.85)

        # Should still store in memory
        assert cache.memory_cache["test_key"] == 0.85

    @pytest.mark.asyncio
    async def test_clear_redis_success(self):
        """Test clear removes all Redis keys."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        # First scan returns keys, second returns empty
        mock_redis.scan = AsyncMock(
            side_effect=[
                (1, ["lats:eval:key1", "lats:eval:key2"]),
                (0, []),
            ]
        )
        mock_redis.delete = AsyncMock()

        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["key1"] = 0.5

        await cache.clear()

        assert mock_redis.delete.called
        assert cache.memory_cache == {}

    @pytest.mark.asyncio
    async def test_clear_redis_error(self):
        """Test clear still clears memory on Redis error."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(side_effect=Exception("Redis scan error"))

        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["key1"] = 0.5

        await cache.clear()

        # Memory should still be cleared
        assert cache.memory_cache == {}

    def test_get_stats_with_redis(self):
        """Test get_stats with Redis enabled."""
        from src.caching.redis_cache import RedisEvalCache

        mock_redis = MagicMock()
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["key1"] = 0.5

        stats = cache.get_stats()

        assert stats["memory_entries"] == 1
        assert stats["using_redis"] == 1
