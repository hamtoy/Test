"""Tests for RedisEvalCache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.caching.redis_cache import RedisEvalCache


class TestRedisEvalCacheInit:
    """Tests for RedisEvalCache initialization."""

    def test_init_without_redis(self) -> None:
        """Test initialization without Redis client."""
        cache = RedisEvalCache()
        assert cache.use_redis is False
        assert cache.memory_cache == {}
        assert cache.ttl > 0

    def test_init_with_redis(self) -> None:
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        cache = RedisEvalCache(redis_client=mock_redis)
        assert cache.use_redis is True
        assert cache.redis is mock_redis

    def test_init_custom_ttl(self) -> None:
        """Test initialization with custom TTL."""
        cache = RedisEvalCache(ttl=7200)
        assert cache.ttl == 7200


class TestRedisEvalCacheGet:
    """Tests for RedisEvalCache.get method."""

    @pytest.mark.asyncio
    async def test_get_from_memory_cache(self) -> None:
        """Test get falls back to memory when no Redis."""
        cache = RedisEvalCache()
        cache.memory_cache["test_key"] = 0.95

        result = await cache.get("test_key")

        assert result == 0.95

    @pytest.mark.asyncio
    async def test_get_missing_key(self) -> None:
        """Test get returns None for missing key."""
        cache = RedisEvalCache()

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_from_redis(self) -> None:
        """Test get retrieves from Redis."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0.85"
        cache = RedisEvalCache(redis_client=mock_redis)

        result = await cache.get("test_key")

        assert result == 0.85
        mock_redis.get.assert_called_once_with("lats:eval:test_key")

    @pytest.mark.asyncio
    async def test_get_redis_returns_none(self) -> None:
        """Test get when Redis returns None."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        cache = RedisEvalCache(redis_client=mock_redis)

        result = await cache.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_redis_error_fallback(self) -> None:
        """Test get falls back to memory on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis connection error")
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["test_key"] = 0.75

        result = await cache.get("test_key")

        assert result == 0.75


class TestRedisEvalCacheSet:
    """Tests for RedisEvalCache.set method."""

    @pytest.mark.asyncio
    async def test_set_memory_only(self) -> None:
        """Test set stores in memory when no Redis."""
        cache = RedisEvalCache()

        await cache.set("test_key", 0.9)

        assert cache.memory_cache["test_key"] == 0.9

    @pytest.mark.asyncio
    async def test_set_with_redis(self) -> None:
        """Test set stores in both Redis and memory."""
        mock_redis = AsyncMock()
        cache = RedisEvalCache(redis_client=mock_redis, ttl=3600)

        await cache.set("test_key", 0.88)

        mock_redis.setex.assert_called_once_with("lats:eval:test_key", 3600, "0.88")
        assert cache.memory_cache["test_key"] == 0.88

    @pytest.mark.asyncio
    async def test_set_redis_error_fallback(self) -> None:
        """Test set falls back to memory on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis write error")
        cache = RedisEvalCache(redis_client=mock_redis)

        await cache.set("test_key", 0.77)

        assert cache.memory_cache["test_key"] == 0.77


class TestRedisEvalCacheClear:
    """Tests for RedisEvalCache.clear method."""

    @pytest.mark.asyncio
    async def test_clear_memory_only(self) -> None:
        """Test clear clears memory cache."""
        cache = RedisEvalCache()
        cache.memory_cache["key1"] = 0.5
        cache.memory_cache["key2"] = 0.6

        await cache.clear()

        assert cache.memory_cache == {}

    @pytest.mark.asyncio
    async def test_clear_with_redis(self) -> None:
        """Test clear deletes Redis keys and memory."""
        mock_redis = AsyncMock()
        mock_redis.scan.return_value = (0, ["lats:eval:key1", "lats:eval:key2"])
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["key1"] = 0.5

        await cache.clear()

        mock_redis.delete.assert_called_once()
        assert cache.memory_cache == {}

    @pytest.mark.asyncio
    async def test_clear_redis_error(self) -> None:
        """Test clear handles Redis error gracefully."""
        mock_redis = AsyncMock()
        mock_redis.scan.side_effect = Exception("Redis error")
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["key1"] = 0.5

        await cache.clear()

        # Memory should still be cleared
        assert cache.memory_cache == {}


class TestRedisEvalCacheStats:
    """Tests for RedisEvalCache.get_stats method."""

    def test_get_stats_memory_only(self) -> None:
        """Test stats without Redis."""
        cache = RedisEvalCache()
        cache.memory_cache["k1"] = 0.1
        cache.memory_cache["k2"] = 0.2

        stats = cache.get_stats()

        assert stats["memory_entries"] == 2
        assert stats["using_redis"] == 0

    def test_get_stats_with_redis(self) -> None:
        """Test stats with Redis."""
        mock_redis = MagicMock()
        cache = RedisEvalCache(redis_client=mock_redis)

        stats = cache.get_stats()

        assert stats["using_redis"] == 1


class TestRedisEvalCacheGetMany:
    """Tests for RedisEvalCache.get_many method."""

    @pytest.mark.asyncio
    async def test_get_many_empty_keys(self) -> None:
        """Test get_many with empty key list."""
        cache = RedisEvalCache()

        result = await cache.get_many([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_many_memory_only(self) -> None:
        """Test get_many from memory cache."""
        cache = RedisEvalCache()
        cache.memory_cache["k1"] = 0.1
        cache.memory_cache["k2"] = 0.2

        result = await cache.get_many(["k1", "k2", "k3"])

        assert result == [0.1, 0.2, None]

    @pytest.mark.asyncio
    async def test_get_many_with_redis(self) -> None:
        """Test get_many falls back to memory when Redis pipeline fails."""
        # Testing the fallback path since pipeline mocking is complex
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Mock pipeline not supported")
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["k1"] = 0.5
        cache.memory_cache["k3"] = 0.7

        result = await cache.get_many(["k1", "k2", "k3"])

        assert result == [0.5, None, 0.7]

    @pytest.mark.asyncio
    async def test_get_many_redis_error_fallback(self) -> None:
        """Test get_many falls back to memory on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Pipeline error")
        cache = RedisEvalCache(redis_client=mock_redis)
        cache.memory_cache["k1"] = 0.3

        result = await cache.get_many(["k1", "k2"])

        assert result == [0.3, None]


class TestRedisEvalCacheSetMany:
    """Tests for RedisEvalCache.set_many method."""

    @pytest.mark.asyncio
    async def test_set_many_empty_items(self) -> None:
        """Test set_many with empty items."""
        cache = RedisEvalCache()

        await cache.set_many({})

        assert cache.memory_cache == {}

    @pytest.mark.asyncio
    async def test_set_many_memory_only(self) -> None:
        """Test set_many stores in memory."""
        cache = RedisEvalCache()

        await cache.set_many({"k1": 0.1, "k2": 0.2})

        assert cache.memory_cache == {"k1": 0.1, "k2": 0.2}

    @pytest.mark.asyncio
    async def test_set_many_with_redis(self) -> None:
        """Test set_many stores in memory even when Redis pipeline fails."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Mock pipeline not supported")
        cache = RedisEvalCache(redis_client=mock_redis, ttl=3600)

        await cache.set_many({"k1": 0.1, "k2": 0.2})

        # Memory should still be updated via fallback
        assert cache.memory_cache == {"k1": 0.1, "k2": 0.2}

    @pytest.mark.asyncio
    async def test_set_many_redis_error_fallback(self) -> None:
        """Test set_many falls back to memory on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Pipeline error")
        cache = RedisEvalCache(redis_client=mock_redis)

        await cache.set_many({"k1": 0.4, "k2": 0.5})

        assert cache.memory_cache == {"k1": 0.4, "k2": 0.5}
