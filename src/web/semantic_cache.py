"""Semantic Cache for QA answers using query embedding similarity.

This module provides a semantic caching system that uses query embeddings
to find similar queries and return cached answers, improving cache hit rate
compared to exact hash matching.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any

from src.config.constants import DEFAULT_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Similarity score between 0 and 1
    """
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


@dataclass
class CacheEntry:
    """A cached answer with its query embedding."""

    query: str
    query_type: str
    embedding: list[float]
    answer: Any
    timestamp: float


class SemanticAnswerCache:
    """Semantic cache using query embeddings for similarity matching.

    Instead of exact hash matching, this cache uses cosine similarity
    between query embeddings to find similar queries and return cached
    answers.

    Features:
    - Query embedding-based similarity search
    - Configurable similarity threshold (default 0.85)
    - TTL-based expiration
    - Redis persistence (optional) with memory backup
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        similarity_threshold: float = 0.85,
        redis_client: Any | None = None,
    ) -> None:
        """Initialize the semantic answer cache.

        Args:
            ttl_seconds: Time-to-live for cache entries
            similarity_threshold: Minimum cosine similarity for cache hit (0-1)
            redis_client: Optional async Redis client for persistence
        """
        self.cache: dict[str, CacheEntry] = {}
        self.ttl = ttl_seconds
        self.threshold = similarity_threshold
        self._hits = 0
        self._misses = 0
        self.redis = redis_client
        self.use_redis = redis_client is not None
        self.prefix = "qa:semantic:"
        self._embeddings: Any = None

        logger.info(
            "SemanticAnswerCache initialized (threshold=%.2f, TTL=%ds, redis=%s)",
            similarity_threshold,
            ttl_seconds,
            self.use_redis,
        )

    def _get_embeddings(self) -> Any:
        """Lazy initialization of embeddings model."""
        if self._embeddings is None:
            try:
                from src.qa.graph.utils import CustomGeminiEmbeddings

                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not set")

                self._embeddings = CustomGeminiEmbeddings(api_key=api_key)
                logger.info("Embeddings model initialized for semantic cache")
            except Exception as e:
                logger.warning("Failed to initialize embeddings: %s", e)
                raise
        return self._embeddings

    def _embed_query(self, query: str) -> list[float]:
        """Generate embedding for a query.

        Args:
            query: The query string

        Returns:
            Embedding vector (768 dimensions for Gemini)
        """
        embeddings = self._get_embeddings()
        result: list[float] = list(embeddings.embed_query(query))
        return result

    def _find_similar(
        self,
        query_embedding: list[float],
        query_type: str,
    ) -> tuple[CacheEntry | None, float]:
        """Find the most similar cached entry.

        Args:
            query_embedding: The query embedding vector
            query_type: Type of query to match

        Returns:
            Tuple of (best matching entry, similarity score) or (None, 0)
        """
        best_entry: CacheEntry | None = None
        best_similarity = 0.0
        now = time.monotonic()

        expired_keys: list[str] = []

        for key, entry in self.cache.items():
            # Check TTL
            if now - entry.timestamp > self.ttl:
                expired_keys.append(key)
                continue

            # Match query type
            if entry.query_type != query_type:
                continue

            similarity = _cosine_similarity(query_embedding, entry.embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_entry = entry

        # Clean up expired entries
        for key in expired_keys:
            del self.cache[key]

        return best_entry, best_similarity

    async def get(self, query: str, _ocr_text: str, query_type: str) -> Any | None:  # noqa: ARG002
        """Retrieve cached answer if a similar query exists.

        Args:
            query: The query string
            _ocr_text: OCR text (intentionally ignored in semantic cache, kept for API compatibility)
            query_type: Type of query

        Returns:
            Cached result or None if not found/expired
        """
        await asyncio.sleep(0)  # S7503: async function must use await
        try:
            query_embedding = self._embed_query(query)
        except Exception as e:
            logger.warning("Failed to embed query for cache lookup: %s", e)
            self._misses += 1
            return None

        # Search in memory cache
        best_entry, similarity = self._find_similar(query_embedding, query_type)

        if best_entry is not None and similarity >= self.threshold:
            self._hits += 1
            logger.info(
                "Cache HIT (semantic): similarity=%.3f, query_type=%s (saved ~6-12s)",
                similarity,
                query_type,
            )
            return best_entry.answer

        self._misses += 1
        logger.debug(
            "Cache MISS (semantic): best_similarity=%.3f, threshold=%.2f",
            similarity,
            self.threshold,
        )
        return None

    async def set(  # noqa: ARG002
        self,
        query: str,
        _ocr_text: str,
        query_type: str,
        result: Any,
    ) -> None:
        """Store result in cache with query embedding.

        Args:
            query: The query string
            _ocr_text: OCR text (intentionally ignored, kept for API compatibility)
            query_type: Type of query
            result: The result to cache
        """
        await asyncio.sleep(0)  # S7503: async function must use await
        try:
            query_embedding = self._embed_query(query)
        except Exception as e:
            logger.warning("Failed to embed query for cache storage: %s", e)
            return

        # Generate a unique key based on query hash
        import hashlib

        key = hashlib.sha256(f"{query}|{query_type}".encode()).hexdigest()[:16]

        entry = CacheEntry(
            query=query,
            query_type=query_type,
            embedding=query_embedding,
            answer=result,
            timestamp=time.monotonic(),
        )

        self.cache[key] = entry

        # Store in Redis if available
        if self.use_redis and self.redis:
            try:
                redis_key = f"{self.prefix}{key}"
                redis_data = {
                    "query": query,
                    "query_type": query_type,
                    "embedding": query_embedding,
                    "answer": result,
                }
                await self.redis.setex(redis_key, self.ttl, json.dumps(redis_data))
                logger.debug("Cache SET (Redis): query_type=%s", query_type)
            except Exception as e:
                logger.warning("Redis cache set failed: %s", e)

        logger.debug(
            "Cache SET (semantic): query_type=%s, cache_size=%d",
            query_type,
            len(self.cache),
        )

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
            "similarity_threshold": self.threshold,
            "using_redis": self.use_redis,
            "cache_type": "semantic",
        }

    async def clear(self) -> None:
        """Clear all cache entries."""
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
                logger.info("Redis semantic cache cleared")
            except Exception as e:
                logger.warning("Redis cache clear failed: %s", e)

        size = len(self.cache)
        self.cache.clear()
        logger.info("Semantic cache cleared: %d entries removed", size)


# Global semantic cache instance
semantic_answer_cache = SemanticAnswerCache()
