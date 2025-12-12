"""Tests for cache analytics helpers."""

import json
from pathlib import Path

import pytest

from src.caching.analytics import (
    CacheMetrics,
    analyze_cache_stats,
    get_unified_cache_report,
)


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


class TestAnalyzeCacheStats:
    """Tests for analyze_cache_stats function."""

    def test_correct_aggregation(self, tmp_path: Path) -> None:
        """Correctly aggregates hits, misses, and savings from JSONL."""
        stats_file = tmp_path / "cache_stats.jsonl"
        records = [
            {"cache_hits": 5, "cache_misses": 2},
            {"cache_hits": 3, "cache_misses": 1},
            {"cache_hits": 2, "cache_misses": 0},
        ]
        stats_file.write_text(
            "\n".join(json.dumps(r) for r in records), encoding="utf-8"
        )

        result = analyze_cache_stats(stats_file)

        assert result["total_records"] == 3
        assert result["total_hits"] == 10  # 5 + 3 + 2
        assert result["total_misses"] == 3  # 2 + 1 + 0
        assert result["hit_rate"] == pytest.approx(76.92, rel=0.1)  # 10 / 13 * 100

    def test_malformed_lines_ignored(self, tmp_path: Path) -> None:
        """Malformed JSON lines are skipped without exception."""
        stats_file = tmp_path / "cache_stats.jsonl"
        content = """{"cache_hits": 2, "cache_misses": 1}
not valid json
{"cache_hits": 3, "cache_misses": 0}

{"invalid_field":
{"cache_hits": 1, "cache_misses": 1}"""
        stats_file.write_text(content, encoding="utf-8")

        result = analyze_cache_stats(stats_file)

        # Only 3 valid records should be processed
        assert result["total_records"] == 3
        assert result["total_hits"] == 6  # 2 + 3 + 1
        assert result["total_misses"] == 2  # 1 + 0 + 1

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns zero counts."""
        stats_file = tmp_path / "cache_stats.jsonl"
        stats_file.write_text("", encoding="utf-8")

        result = analyze_cache_stats(stats_file)

        assert result["total_records"] == 0
        assert result["total_hits"] == 0
        assert result["total_misses"] == 0
        assert result["hit_rate"] == 0.0

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for missing file."""
        missing_file = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError):
            analyze_cache_stats(missing_file)

    def test_output_keys_stable(self, tmp_path: Path) -> None:
        """Output contains the expected keys."""
        stats_file = tmp_path / "cache_stats.jsonl"
        stats_file.write_text('{"cache_hits": 1, "cache_misses": 0}', encoding="utf-8")

        result = analyze_cache_stats(stats_file)

        expected_keys = {
            "total_records",
            "total_hits",
            "total_misses",
            "hit_rate",
            "estimated_savings_usd",
        }
        assert set(result.keys()) == expected_keys
