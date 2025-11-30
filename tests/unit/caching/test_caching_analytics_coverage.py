"""Additional tests for src/caching/analytics.py to improve coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.caching.analytics import (
    CacheAnalytics,
    MemoryMonitor,
    RealTimeTracker,
    analyze_cache_stats,
    print_cache_report,
    print_realtime_report,
)


class TestPrintReports:
    """Test print functions for analytics."""

    def test_print_cache_report(self) -> None:
        """Test print_cache_report function."""
        summary = {
            "total_records": 100,
            "hit_rate": 75.0,
            "total_hits": 75,
            "total_misses": 25,
            "estimated_savings_usd": 0.0050,
        }

        # Should not raise
        with patch("src.caching.analytics.Console") as mock_console:
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            print_cache_report(summary)

            mock_console_instance.print.assert_called_once()

    def test_print_realtime_report(self) -> None:
        """Test print_realtime_report function."""
        analytics = CacheAnalytics(window_size=10)

        # Add some data
        for _ in range(7):
            analytics.record_hit(ttl_usage_ratio=0.5)
        for _ in range(3):
            analytics.record_miss()
        analytics.update_memory(1024 * 1024)  # 1MB

        # Should not raise
        with patch("src.caching.analytics.Console") as mock_console:
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            print_realtime_report(analytics)

            mock_console_instance.print.assert_called_once()

    def test_print_realtime_report_low_hit_rate(self) -> None:
        """Test print_realtime_report with low hit rate (below target)."""
        analytics = CacheAnalytics(window_size=10)

        # Add data with low hit rate
        for _ in range(3):
            analytics.record_hit(ttl_usage_ratio=0.2)
        for _ in range(7):
            analytics.record_miss()
        analytics.update_memory(512 * 1024)  # 512KB

        with patch("src.caching.analytics.Console") as mock_console:
            mock_console_instance = MagicMock()
            mock_console.return_value = mock_console_instance

            print_realtime_report(analytics)

            mock_console_instance.print.assert_called_once()


class TestRealTimeTrackerEdgeCases:
    """Test edge cases for RealTimeTracker."""

    def test_ttl_usage_window_trim(self) -> None:
        """Test TTL usage window trimming."""
        tracker = RealTimeTracker(window_size=5)

        for i in range(10):
            tracker.record_ttl_usage(i * 0.1)

        # Should only keep last 5 values
        assert len(tracker._ttl_usage) == 5

    def test_empty_ttl_efficiency(self) -> None:
        """Test TTL efficiency when no data."""
        tracker = RealTimeTracker(window_size=10)
        assert tracker.ttl_efficiency == 0.0

    def test_empty_hit_rate(self) -> None:
        """Test hit rate when no requests."""
        tracker = RealTimeTracker(window_size=10)
        assert tracker.current_hit_rate == 0.0


class TestMemoryMonitorEdgeCases:
    """Test edge cases for MemoryMonitor."""

    def test_empty_avg_memory(self) -> None:
        """Test average memory when no samples."""
        monitor = MemoryMonitor()
        assert monitor.avg_memory_bytes == 0.0

    def test_memory_trend_decreasing(self) -> None:
        """Test memory trend when usage is decreasing."""
        monitor = MemoryMonitor()

        # Start high, end low
        for i in range(20):
            monitor.record_usage(2000 - i * 50)

        assert monitor.memory_trend == "decreasing"

    def test_memory_sample_trimming(self) -> None:
        """Test that memory samples are trimmed to 1000."""
        monitor = MemoryMonitor()

        for i in range(1100):
            monitor.record_usage(i * 10)

        # Should only keep last 1000 samples
        assert len(monitor._samples) == 1000


class TestAnalyzeCacheStatsEdgeCases:
    """Test edge cases for analyze_cache_stats."""

    def test_analyze_nonexistent_file(self, tmp_path: Path) -> None:
        """Test analyze raises FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="Cache stats file not found"):
            analyze_cache_stats(tmp_path / "nonexistent.jsonl")

    def test_analyze_empty_file(self, tmp_path: Path) -> None:
        """Test analyze with empty file."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        result = analyze_cache_stats(path)
        assert result["total_records"] == 0

    def test_analyze_with_invalid_lines(self, tmp_path: Path) -> None:
        """Test analyze gracefully handles invalid JSON lines."""
        path = tmp_path / "mixed.jsonl"
        content = (
            '{"model":"gemini","cache_hits":5,"cache_misses":2,"input_tokens":1000}\n'
            "invalid json line\n"
            '{"model":"gemini","cache_hits":3,"cache_misses":1,"input_tokens":500}\n'
        )
        path.write_text(content, encoding="utf-8")

        result = analyze_cache_stats(path)
        # Should process valid lines only
        assert result["total_records"] == 2
        assert result["total_hits"] == 8


class TestCacheAnalyticsHitRateTarget:
    """Test hit rate target functionality."""

    def test_hit_rate_no_requests(self) -> None:
        """Test hit rate target with no requests."""
        analytics = CacheAnalytics(window_size=10)
        # No requests means 0% hit rate
        assert analytics.is_hit_rate_target_met(0.0) is True
        assert analytics.is_hit_rate_target_met(10.0) is False

    def test_hit_with_ttl_usage(self) -> None:
        """Test recording hit with TTL usage."""
        analytics = CacheAnalytics(window_size=10)
        analytics.record_hit(ttl_usage_ratio=0.75)

        assert analytics.metrics.hits == 1
        assert analytics.tracker.ttl_efficiency == 75.0

    def test_hit_without_ttl_usage(self) -> None:
        """Test recording hit without TTL usage."""
        analytics = CacheAnalytics(window_size=10)
        analytics.record_hit()

        assert analytics.metrics.hits == 1
        # TTL efficiency should remain 0 (no data)
        assert analytics.tracker.ttl_efficiency == 0.0
