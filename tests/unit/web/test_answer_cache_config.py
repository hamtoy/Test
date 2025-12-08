"""Tests for answer cache configuration and TTL optimization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path for direct imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config.constants import (  # noqa: E402
    DEFAULT_CACHE_TTL_SECONDS,
    QA_CACHE_OCR_TRUNCATE_LENGTH,
    QA_GENERATION_OCR_TRUNCATE_LENGTH,
)

# Import AnswerCache directly from the module file to avoid FastAPI dependency
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "cache_module",
    project_root / "src" / "web" / "cache.py",
)
cache_module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(cache_module)  # type: ignore[union-attr]

AnswerCache = cache_module.AnswerCache
answer_cache = cache_module.answer_cache


class TestCacheConfiguration:
    """Tests for cache configuration constants and optimization."""

    def test_cache_ttl_optimized(self) -> None:
        """Test that cache TTL is set to 4 hours (14400s) for better hit rate."""
        assert DEFAULT_CACHE_TTL_SECONDS == 14400, (
            f"Cache TTL should be 14400s (4 hours), got {DEFAULT_CACHE_TTL_SECONDS}s"
        )

    def test_ocr_truncate_lengths_synced(self) -> None:
        """Test that QA_CACHE_OCR_TRUNCATE_LENGTH matches QA_GENERATION_OCR_TRUNCATE_LENGTH."""
        assert QA_CACHE_OCR_TRUNCATE_LENGTH == QA_GENERATION_OCR_TRUNCATE_LENGTH == 3000, (
            f"OCR truncate lengths must match at 3000. "
            f"Cache: {QA_CACHE_OCR_TRUNCATE_LENGTH}, Generation: {QA_GENERATION_OCR_TRUNCATE_LENGTH}"
        )

    def test_global_cache_uses_constant(self) -> None:
        """Test that global answer_cache instance uses DEFAULT_CACHE_TTL_SECONDS."""
        assert answer_cache.ttl == DEFAULT_CACHE_TTL_SECONDS, (
            f"Global answer_cache should use DEFAULT_CACHE_TTL_SECONDS ({DEFAULT_CACHE_TTL_SECONDS}), "
            f"got {answer_cache.ttl}"
        )

    def test_cache_initialization_with_custom_ttl(self) -> None:
        """Test that AnswerCache can be initialized with custom TTL."""
        custom_cache = AnswerCache(ttl_seconds=7200)
        assert custom_cache.ttl == 7200

    def test_cache_initialization_with_default(self) -> None:
        """Test that AnswerCache defaults to DEFAULT_CACHE_TTL_SECONDS when no TTL provided."""
        default_cache = AnswerCache()
        assert default_cache.ttl == DEFAULT_CACHE_TTL_SECONDS


class TestCacheKeyGeneration:
    """Tests for cache key generation and consistency."""

    def test_cache_key_generation(self) -> None:
        """Test that cache keys are generated consistently."""
        cache = AnswerCache()
        query = "테스트 질문"
        ocr_text = "OCR 텍스트" * 100
        query_type = "explanation"

        key1 = cache._make_key(query, ocr_text, query_type)
        key2 = cache._make_key(query, ocr_text, query_type)

        assert key1 == key2, "Same inputs should generate same cache key"

    def test_cache_key_different_for_different_inputs(self) -> None:
        """Test that different inputs generate different cache keys."""
        cache = AnswerCache()
        query = "테스트 질문"
        ocr_text = "OCR 텍스트"

        key1 = cache._make_key(query, ocr_text, "explanation")
        key2 = cache._make_key(query, ocr_text, "reasoning")

        assert key1 != key2, "Different query types should generate different keys"


class TestCacheStats:
    """Tests for cache statistics tracking."""

    def test_cache_stats_initial_state(self) -> None:
        """Test cache statistics in initial state."""
        cache = AnswerCache()
        stats = cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_requests"] == 0
        assert stats["hit_rate_percent"] == 0.0
        assert stats["cache_size"] == 0
        assert stats["ttl_seconds"] == DEFAULT_CACHE_TTL_SECONDS

    def test_cache_stats_after_miss(self) -> None:
        """Test cache statistics after a cache miss."""
        cache = AnswerCache()

        result = cache.get("test query", "test ocr", "explanation")
        assert result is None

        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["total_requests"] == 1

    def test_cache_stats_after_hit(self) -> None:
        """Test cache statistics after a cache hit."""
        cache = AnswerCache()

        # Store a value
        cache.set("test query", "test ocr", "explanation", {"answer": "test"})

        # Retrieve it
        result = cache.get("test query", "test ocr", "explanation")
        assert result is not None

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["cache_size"] == 1
        assert stats["hit_rate_percent"] == 100.0


class TestCacheTTLExpiration:
    """Tests for cache TTL expiration behavior."""

    def test_cache_expiration_logic(self) -> None:
        """Test that expired entries are not returned."""
        # Use very short TTL for testing
        cache = AnswerCache(ttl_seconds=1)

        cache.set("test query", "test ocr", "explanation", {"answer": "test"})

        # Immediate retrieval should work
        result = cache.get("test query", "test ocr", "explanation")
        assert result is not None

        # Wait for expiration (simulate by directly checking the logic)
        import time

        time.sleep(1.1)

        # Should return None after expiration
        result = cache.get("test query", "test ocr", "explanation")
        assert result is None

    def test_clear_expired_entries(self) -> None:
        """Test manual clearing of expired entries."""
        cache = AnswerCache(ttl_seconds=1)

        cache.set("query1", "ocr1", "explanation", {"answer": "test1"})
        cache.set("query2", "ocr2", "reasoning", {"answer": "test2"})

        import time

        time.sleep(1.1)

        # Clear expired entries
        cleared = cache.clear_expired()
        assert cleared == 2
        assert cache.get_stats()["cache_size"] == 0
