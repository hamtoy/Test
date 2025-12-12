"""Tests for PerformanceTracker."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.infra.performance_tracker import (
    PerformanceMetric,
    PerformanceTracker,
    get_tracker,
)


def test_record_and_get_stats_by_operation() -> None:
    tracker = PerformanceTracker(window_minutes=60)
    now = datetime.now(timezone.utc)

    tracker.record(
        PerformanceMetric(
            operation="query_generation",
            duration_ms=100,
            tokens_used=10,
            cache_hit=False,
            timestamp=now,
            status="success",
        ),
    )
    tracker.record(
        PerformanceMetric(
            operation="query_generation",
            duration_ms=200,
            tokens_used=5,
            cache_hit=True,
            timestamp=now,
            status="retry",
        ),
    )
    tracker.record(
        PerformanceMetric(
            operation="evaluation",
            duration_ms=50,
            tokens_used=2,
            cache_hit=False,
            timestamp=now,
            status="success",
        ),
    )

    stats_all = tracker.get_stats()
    assert set(stats_all.keys()) == {"query_generation", "evaluation"}

    q_stats = stats_all["query_generation"]
    assert q_stats["count"] == 2.0
    assert q_stats["min_duration_ms"] == 100
    assert q_stats["max_duration_ms"] == 200
    assert q_stats["avg_duration_ms"] == 150
    assert q_stats["cache_hit_rate"] == 0.5
    assert q_stats["success_rate"] == 0.5

    e_stats = stats_all["evaluation"]
    assert e_stats["count"] == 1.0
    assert e_stats["success_rate"] == 1.0

    stats_filtered = tracker.get_stats(operation="evaluation")
    assert list(stats_filtered.keys()) == ["evaluation"]


def test_cleanup_old_metrics() -> None:
    tracker = PerformanceTracker(window_minutes=1)
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(minutes=5)

    tracker.record(
        PerformanceMetric(
            operation="query_generation",
            duration_ms=10,
            tokens_used=1,
            cache_hit=False,
            timestamp=old_time,
            status="success",
        ),
    )
    assert tracker.metrics == []

    tracker.record(
        PerformanceMetric(
            operation="query_generation",
            duration_ms=20,
            tokens_used=1,
            cache_hit=False,
            timestamp=now,
            status="success",
        ),
    )
    assert len(tracker.metrics) == 1


def test_global_tracker_singleton() -> None:
    assert get_tracker() is get_tracker()
