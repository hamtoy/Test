"""Tests for real-time cache analytics features."""
from typing import Any

import pytest

from src.caching.analytics import (
    CacheAnalytics,
    CacheMetrics,
    MemoryMonitor,
    RealTimeTracker,
)


class TestCacheMetrics:
    """Test CacheMetrics dataclass."""

    def test_hit_rate_calculation(self) -> None:
        metrics = CacheMetrics(hits=70, misses=30)
        assert metrics.hit_rate == 70.0

    def test_hit_rate_with_no_requests(self) -> None:
        metrics = CacheMetrics(hits=0, misses=0)
        assert metrics.hit_rate == 0.0

    def test_total_requests(self) -> None:
        metrics = CacheMetrics(hits=50, misses=50)
        assert metrics.total_requests == 100


class TestRealTimeTracker:
    """Test RealTimeTracker sliding window."""

    def test_record_hit(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        tracker.record_hit()
        assert tracker.current_hit_rate == 100.0

    def test_record_miss(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        tracker.record_miss()
        assert tracker.current_hit_rate == 0.0

    def test_mixed_hits_misses(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        for _ in range(7):
            tracker.record_hit()
        for _ in range(3):
            tracker.record_miss()
        assert tracker.current_hit_rate == 70.0

    def test_window_trim(self) -> None:
        tracker = RealTimeTracker(window_size=5)
        for _ in range(10):
            tracker.record_hit()
        # Should only have last 5 in window
        assert len(tracker._requests) == 5

    def test_ttl_usage_tracking(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        tracker.record_ttl_usage(0.5)
        tracker.record_ttl_usage(0.7)
        assert tracker.ttl_efficiency == 60.0

    def test_ttl_usage_clamping(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        tracker.record_ttl_usage(1.5)  # Should clamp to 1.0
        tracker.record_ttl_usage(-0.5)  # Should clamp to 0.0
        assert tracker.ttl_efficiency == 50.0

    def test_requests_per_second_empty(self) -> None:
        tracker = RealTimeTracker(window_size=10)
        assert tracker.requests_per_second == 0.0


class TestMemoryMonitor:
    """Test MemoryMonitor."""

    def test_record_usage(self) -> None:
        monitor = MemoryMonitor()
        monitor.record_usage(1024)
        assert monitor.current_memory_bytes == 1024
        assert monitor.max_memory_bytes == 1024

    def test_max_memory_tracking(self) -> None:
        monitor = MemoryMonitor()
        monitor.record_usage(1024)
        monitor.record_usage(2048)
        monitor.record_usage(1024)
        assert monitor.max_memory_bytes == 2048
        assert monitor.current_memory_bytes == 1024

    def test_avg_memory(self) -> None:
        monitor = MemoryMonitor()
        monitor.record_usage(1000)
        monitor.record_usage(2000)
        monitor.record_usage(3000)
        assert monitor.avg_memory_bytes == 2000.0

    def test_memory_trend_insufficient_data(self) -> None:
        monitor = MemoryMonitor()
        for i in range(5):
            monitor.record_usage(1000 + i)
        assert monitor.memory_trend == "insufficient_data"

    def test_memory_trend_stable(self) -> None:
        monitor = MemoryMonitor()
        for i in range(20):
            monitor.record_usage(1000)
        assert monitor.memory_trend == "stable"

    def test_memory_trend_increasing(self) -> None:
        monitor = MemoryMonitor()
        for i in range(20):
            monitor.record_usage(1000 + i * 100)
        assert monitor.memory_trend == "increasing"


class TestCacheAnalytics:
    """Test CacheAnalytics comprehensive tracking."""

    def test_record_hit(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        analytics.record_hit()
        assert analytics.metrics.hits == 1

    def test_record_miss(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        analytics.record_miss()
        assert analytics.metrics.misses == 1

    def test_record_eviction(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        analytics.record_eviction()
        assert analytics.metrics.evictions == 1

    def test_record_ttl_expiration(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        analytics.record_ttl_expiration()
        assert analytics.metrics.ttl_expirations == 1

    def test_update_memory(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        analytics.update_memory(1024 * 1024)
        assert analytics.metrics.memory_bytes == 1024 * 1024

    def test_get_summary(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        for _ in range(7):
            analytics.record_hit(ttl_usage_ratio=0.6)
        for _ in range(3):
            analytics.record_miss()
        analytics.update_memory(1024)

        summary = analytics.get_summary()
        assert summary["total_hits"] == 7
        assert summary["total_misses"] == 3
        assert summary["total_requests"] == 10
        assert summary["overall_hit_rate"] == 70.0
        assert summary["realtime_hit_rate"] == 70.0
        assert summary["current_memory_bytes"] == 1024

    def test_is_hit_rate_target_met(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        for _ in range(7):
            analytics.record_hit()
        for _ in range(3):
            analytics.record_miss()
        
        assert analytics.is_hit_rate_target_met(70.0) is True
        assert analytics.is_hit_rate_target_met(80.0) is False

    def test_hit_rate_target_not_met(self) -> None:
        analytics = CacheAnalytics(window_size=10)
        for _ in range(5):
            analytics.record_hit()
        for _ in range(5):
            analytics.record_miss()
        
        assert analytics.is_hit_rate_target_met(70.0) is False


class TestCachingInitExports:
    """Test that new exports are available from caching package."""

    def test_cache_analytics_import(self) -> None:
        from src.caching import CacheAnalytics
        assert CacheAnalytics is not None

    def test_cache_metrics_import(self) -> None:
        from src.caching import CacheMetrics
        assert CacheMetrics is not None

    def test_realtime_tracker_import(self) -> None:
        from src.caching import RealTimeTracker
        assert RealTimeTracker is not None

    def test_memory_monitor_import(self) -> None:
        from src.caching import MemoryMonitor
        assert MemoryMonitor is not None

    def test_print_realtime_report_import(self) -> None:
        from src.caching import print_realtime_report
        assert print_realtime_report is not None
