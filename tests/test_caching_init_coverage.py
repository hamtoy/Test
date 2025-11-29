"""Tests for src/caching/__init__.py lazy import coverage."""


class TestCachingPackageLazyImports:
    """Test lazy imports in src.caching package."""

    def test_caching_layer_lazy_import(self) -> None:
        """Test lazy import of CachingLayer."""
        from src.caching import CachingLayer

        assert CachingLayer is not None
        assert hasattr(CachingLayer, "__init__")

    def test_analyze_cache_stats_lazy_import(self) -> None:
        """Test lazy import of analyze_cache_stats."""
        from src.caching import analyze_cache_stats

        assert analyze_cache_stats is not None
        assert callable(analyze_cache_stats)

    def test_print_cache_report_lazy_import(self) -> None:
        """Test lazy import of print_cache_report."""
        from src.caching import print_cache_report

        assert print_cache_report is not None
        assert callable(print_cache_report)

    def test_redis_eval_cache_lazy_import(self) -> None:
        """Test lazy import of RedisEvalCache."""
        from src.caching import RedisEvalCache

        assert RedisEvalCache is not None
        assert hasattr(RedisEvalCache, "__init__")

    def test_unknown_attribute_raises_error(self) -> None:
        """Test that unknown attribute raises AttributeError."""
        import pytest
        import src.caching

        with pytest.raises(AttributeError) as exc_info:
            _ = src.caching.nonexistent_function  # noqa: B018

        assert "nonexistent_function" in str(exc_info.value)

    def test_all_exports(self) -> None:
        """Test that __all__ contains expected exports."""
        import src.caching

        assert "CachingLayer" in src.caching.__all__
        assert "analyze_cache_stats" in src.caching.__all__
        assert "print_cache_report" in src.caching.__all__
        assert "RedisEvalCache" in src.caching.__all__
