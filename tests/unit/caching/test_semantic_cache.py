"""Tests for SemanticAnswerCache."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest


class TestCosineSimilarity:
    """Tests for cosine similarity function."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity of 1.0."""
        from src.web.semantic_cache import _cosine_similarity

        vec = [1.0, 2.0, 3.0]
        assert math.isclose(_cosine_similarity(vec, vec), 1.0, rel_tol=1e-9)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity of 0.0."""
        from src.web.semantic_cache import _cosine_similarity

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert math.isclose(_cosine_similarity(vec1, vec2), 0.0, rel_tol=1e-9)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors should have similarity of -1.0."""
        from src.web.semantic_cache import _cosine_similarity

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        assert math.isclose(_cosine_similarity(vec1, vec2), -1.0, rel_tol=1e-9)

    def test_different_lengths(self) -> None:
        """Different length vectors should return 0.0."""
        from src.web.semantic_cache import _cosine_similarity

        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec1, vec2) == 0.0

    def test_zero_vector(self) -> None:
        """Zero vector should return 0.0."""
        from src.web.semantic_cache import _cosine_similarity

        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec1, vec2) == 0.0


class TestSemanticAnswerCacheInit:
    """Tests for SemanticAnswerCache initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        from src.web.semantic_cache import SemanticAnswerCache

        cache = SemanticAnswerCache()
        assert cache.threshold == 0.85
        assert cache.use_redis is False
        assert cache.cache == {}
        assert cache._hits == 0
        assert cache._misses == 0

    def test_init_custom_threshold(self) -> None:
        """Test initialization with custom threshold."""
        from src.web.semantic_cache import SemanticAnswerCache

        cache = SemanticAnswerCache(similarity_threshold=0.90)
        assert cache.threshold == 0.90

    def test_init_with_redis(self) -> None:
        """Test initialization with Redis client."""
        from src.web.semantic_cache import SemanticAnswerCache

        mock_redis = MagicMock()
        cache = SemanticAnswerCache(redis_client=mock_redis)
        assert cache.use_redis is True
        assert cache.redis is mock_redis


class TestSemanticAnswerCacheGet:
    """Tests for SemanticAnswerCache.get method."""

    @pytest.mark.asyncio
    async def test_get_cache_miss_empty(self) -> None:
        """Test get returns None on empty cache."""
        from src.web.semantic_cache import SemanticAnswerCache

        cache = SemanticAnswerCache()

        # Mock embedding
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        cache._embeddings = mock_embeddings

        result = await cache.get("test query", "ocr text", "explanation")

        assert result is None
        assert cache._misses == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit_similar_query(self) -> None:
        """Test get returns cached answer for similar query."""
        from src.web.semantic_cache import CacheEntry, SemanticAnswerCache

        cache = SemanticAnswerCache(similarity_threshold=0.85)

        # Create a cached entry
        cached_embedding = [0.1] * 768
        cache.cache["key1"] = CacheEntry(
            query="미 증시 하락 원인",
            query_type="explanation",
            embedding=cached_embedding,
            answer={
                "type": "explanation",
                "query": "미 증시 하락 원인",
                "answer": "답변",
            },
            timestamp=float("inf"),  # Never expires
        )

        # Mock embedding that returns similar vector
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = (
            cached_embedding  # Identical = 1.0 similarity
        )
        cache._embeddings = mock_embeddings

        result = await cache.get("미 증시 하락 이유", "ocr text", "explanation")

        assert result is not None
        assert result["query"] == "미 증시 하락 원인"
        assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_get_cache_miss_different_query_type(self) -> None:
        """Test get returns None when query types don't match."""
        from src.web.semantic_cache import CacheEntry, SemanticAnswerCache

        cache = SemanticAnswerCache()

        # Create a cached entry with different type
        cached_embedding = [0.1] * 768
        cache.cache["key1"] = CacheEntry(
            query="test query",
            query_type="explanation",
            embedding=cached_embedding,
            answer={"answer": "cached"},
            timestamp=float("inf"),
        )

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = cached_embedding
        cache._embeddings = mock_embeddings

        result = await cache.get(
            "test query", "ocr text", "reasoning"
        )  # Different type

        assert result is None
        assert cache._misses == 1


class TestSemanticAnswerCacheSet:
    """Tests for SemanticAnswerCache.set method."""

    @pytest.mark.asyncio
    async def test_set_stores_entry(self) -> None:
        """Test set stores entry in cache."""
        from src.web.semantic_cache import SemanticAnswerCache

        cache = SemanticAnswerCache()

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 768
        cache._embeddings = mock_embeddings

        result = {"type": "explanation", "query": "test", "answer": "answer"}
        await cache.set("test query", "ocr text", "explanation", result)

        assert len(cache.cache) == 1
        entry = list(cache.cache.values())[0]
        assert entry.query == "test query"
        assert entry.query_type == "explanation"
        assert entry.answer == result


class TestSemanticAnswerCacheStats:
    """Tests for SemanticAnswerCache.get_stats method."""

    def test_get_stats(self) -> None:
        """Test get_stats returns correct metrics."""
        from src.web.semantic_cache import SemanticAnswerCache

        cache = SemanticAnswerCache(similarity_threshold=0.85)
        cache._hits = 5
        cache._misses = 15

        stats = cache.get_stats()

        assert stats["hits"] == 5
        assert stats["misses"] == 15
        assert stats["total_requests"] == 20
        assert stats["hit_rate_percent"] == 25.0
        assert stats["similarity_threshold"] == 0.85
        assert stats["cache_type"] == "semantic"


class TestSemanticAnswerCacheClear:
    """Tests for SemanticAnswerCache.clear method."""

    @pytest.mark.asyncio
    async def test_clear_memory(self) -> None:
        """Test clear removes all entries from memory."""
        from src.web.semantic_cache import CacheEntry, SemanticAnswerCache

        cache = SemanticAnswerCache()
        cache.cache["key1"] = CacheEntry(
            query="q1",
            query_type="explanation",
            embedding=[0.1],
            answer={"a": 1},
            timestamp=0,
        )

        await cache.clear()

        assert len(cache.cache) == 0
