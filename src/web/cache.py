"""Answer caching system for QA generation performance optimization.

PHASE 2B: Caching system for ~6-12s reduction on cache hits.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AnswerCache:
    """Cache for generated QA answers.
    
    PHASE 2B: In-memory cache to avoid regenerating identical answers.
    Expected improvement: ~6-12s reduction on cache hits.
    
    Features:
    - MD5-based cache keys from (query, ocr_text, query_type)
    - TTL-based expiration (default 1 hour)
    - Cache hit/miss metrics logging
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize the answer cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 3600 = 1 hour)
        """
        self.cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        logger.info("AnswerCache initialized (TTL: %ds)", ttl_seconds)

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

    def get(self, query: str, ocr_text: str, query_type: str) -> Optional[Any]:
        """Retrieve cached answer if available and not expired.
        
        Args:
            query: The query string
            ocr_text: OCR text content
            query_type: Type of query
            
        Returns:
            Cached result or None if not found/expired
        """
        key = self._make_key(query, ocr_text, query_type)
        if key in self.cache:
            value, timestamp = self.cache[key]
            age = datetime.now().timestamp() - timestamp
            if age < self.ttl:
                self._hits += 1
                logger.info(
                    "Cache HIT: query_type=%s, age=%.1fs (saved ~6-12s)",
                    query_type,
                    age,
                )
                return value
            # Expired - remove it
            del self.cache[key]
            logger.debug("Cache entry expired: query_type=%s, age=%.1fs", query_type, age)
        
        self._misses += 1
        logger.debug("Cache MISS: query_type=%s", query_type)
        return None

    def set(self, query: str, ocr_text: str, query_type: str, result: Any) -> None:
        """Store result in cache.
        
        Args:
            query: The query string
            ocr_text: OCR text content
            query_type: Type of query
            result: The result to cache
        """
        key = self._make_key(query, ocr_text, query_type)
        self.cache[key] = (result, datetime.now().timestamp())
        logger.debug(
            "Cache SET: query_type=%s, cache_size=%d",
            query_type,
            len(self.cache),
        )

    def clear_expired(self) -> int:
        """Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now().timestamp()
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
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        size = len(self.cache)
        self.cache.clear()
        logger.info("Cache cleared: %d entries removed", size)


# Global cache instance (singleton pattern)
answer_cache = AnswerCache(ttl_seconds=3600)
