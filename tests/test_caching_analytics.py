"""Tests for cache analytics helpers."""

from src.caching.analytics import CacheMetrics, get_unified_cache_report


def test_cache_metrics_records_and_reports() -> None:
    """CacheMetrics should track queries and skips."""
    metrics = CacheMetrics(namespace="qa_kg_test")

    metrics.record_query(
        "vector_search", duration_ms=12.5, result_count=3, status="hit"
    )
    metrics.record_query(
        "vector_search", duration_ms=5.0, result_count=0, status="miss"
    )
    metrics.record_skip("vector_store_unavailable")

    summary = metrics.to_summary()
    assert summary["hits"] == 1
    assert summary["misses"] == 1
    assert summary["queries"] == 2
    assert summary["skips"] == 1
    assert summary["last_operation"] is None or summary["last_status"].startswith(
        "skip"
    )

    unified = get_unified_cache_report()
    assert "qa_kg_test" in unified["namespaces"]
    assert unified["namespaces"]["qa_kg_test"]["hits"] == 1
