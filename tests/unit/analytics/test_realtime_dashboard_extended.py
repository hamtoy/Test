"""Comprehensive tests for realtime_dashboard module."""
# mypy: ignore-errors

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.analytics.realtime_dashboard import RealtimeDashboard, get_dashboard


class TestRealtimeDashboard:
    """Tests for RealtimeDashboard class."""

    def test_init_default_retention(self):
        """Test dashboard initialization with default retention."""
        dashboard = RealtimeDashboard()

        assert dashboard.retention_minutes == 60
        assert isinstance(dashboard._metrics, dict)

    def test_init_custom_retention(self):
        """Test dashboard initialization with custom retention."""
        dashboard = RealtimeDashboard(retention_minutes=120)

        assert dashboard.retention_minutes == 120

    @pytest.mark.asyncio
    async def test_record_request_basic(self):
        """Test recording a basic request."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request(
            endpoint="/api/qa",
            latency_ms=150.5,
            tokens_used=100,
            cost_usd=0.001,
            cache_hit=True,
        )

        assert "/api/qa" in dashboard._metrics
        assert len(dashboard._metrics["/api/qa"]) == 1

        metric = dashboard._metrics["/api/qa"][0]
        assert metric["endpoint"] == "/api/qa"
        assert metric["latency_ms"] == 150.5
        assert metric["tokens"] == 100
        assert metric["cost"] == 0.001
        assert metric["cache_hit"] is True

    @pytest.mark.asyncio
    async def test_record_multiple_requests(self):
        """Test recording multiple requests to different endpoints."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/qa", 100.0, 50, 0.001, False)
        await dashboard.record_request("/api/workspace", 200.0, 75, 0.002, True)
        await dashboard.record_request("/api/qa", 150.0, 60, 0.0015, True)

        assert len(dashboard._metrics["/api/qa"]) == 2
        assert len(dashboard._metrics["/api/workspace"]) == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_metrics(self):
        """Test cleanup of old metrics."""
        dashboard = RealtimeDashboard(retention_minutes=0)

        # Record a metric
        await dashboard.record_request("/api/test", 100.0)

        # Wait a bit and record another
        await asyncio.sleep(0.1)
        await dashboard.record_request("/api/test", 200.0)

        # Cleanup should remove old metrics
        await dashboard._cleanup_old_metrics()

        # Since retention is 0, all metrics should be removed
        assert "/api/test" not in dashboard._metrics or len(dashboard._metrics["/api/test"]) == 0

    @pytest.mark.asyncio
    async def test_cleanup_removes_empty_endpoints(self):
        """Test that cleanup removes endpoints with no metrics."""
        dashboard = RealtimeDashboard(retention_minutes=0)

        await dashboard.record_request("/api/test", 100.0)
        
        # Force cleanup
        await dashboard._cleanup_old_metrics()

        # Empty endpoint should be removed
        assert "/api/test" not in dashboard._metrics

    @pytest.mark.asyncio
    async def test_get_summary_empty(self):
        """Test getting summary with no metrics."""
        dashboard = RealtimeDashboard()

        summary = await dashboard.get_summary()

        assert summary["endpoints"] == {}
        assert summary["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_with_metrics(self):
        """Test getting summary with recorded metrics."""
        dashboard = RealtimeDashboard()

        # Record some metrics
        await dashboard.record_request("/api/qa", 100.0, 50, 0.001, True)
        await dashboard.record_request("/api/qa", 200.0, 75, 0.002, False)
        await dashboard.record_request("/api/qa", 150.0, 60, 0.0015, True)

        summary = await dashboard.get_summary()

        assert summary["total_requests"] == 3
        assert "/api/qa" in summary["endpoints"]

        endpoint_stats = summary["endpoints"]["/api/qa"]
        assert endpoint_stats["request_count"] == 3
        assert endpoint_stats["cache_hit_rate"] == 2/3  # 2 out of 3 cache hits

    @pytest.mark.asyncio
    async def test_get_summary_latency_percentiles(self):
        """Test latency percentile calculations."""
        dashboard = RealtimeDashboard()

        # Record metrics with known latencies
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for lat in latencies:
            await dashboard.record_request("/api/test", float(lat))

        summary = await dashboard.get_summary()
        stats = summary["endpoints"]["/api/test"]

        # Check percentiles (allow for index calculation differences)
        assert 40.0 <= stats["latency"]["p50"] <= 60.0
        assert 80.0 <= stats["latency"]["p90"] <= 100.0
        assert 90.0 <= stats["latency"]["p99"] <= 100.0
        assert stats["latency"]["avg"] == 55.0

    @pytest.mark.asyncio
    async def test_get_summary_token_stats(self):
        """Test token usage statistics."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/test", 100.0, tokens_used=100)
        await dashboard.record_request("/api/test", 150.0, tokens_used=200)
        await dashboard.record_request("/api/test", 120.0, tokens_used=150)

        summary = await dashboard.get_summary()
        stats = summary["endpoints"]["/api/test"]

        assert stats["tokens"]["total"] == 450
        assert stats["tokens"]["avg"] == 150.0

    @pytest.mark.asyncio
    async def test_get_summary_cost_stats(self):
        """Test cost statistics."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/test", 100.0, cost_usd=0.01)
        await dashboard.record_request("/api/test", 100.0, cost_usd=0.02)
        await dashboard.record_request("/api/test", 100.0, cost_usd=0.03)

        summary = await dashboard.get_summary()
        stats = summary["endpoints"]["/api/test"]

        assert stats["cost"]["total"] == pytest.approx(0.06)
        assert stats["cost"]["avg"] == pytest.approx(0.02)

    @pytest.mark.asyncio
    async def test_get_summary_multiple_endpoints(self):
        """Test summary with multiple endpoints."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/qa", 100.0, 50, 0.001)
        await dashboard.record_request("/api/qa", 200.0, 60, 0.002)
        await dashboard.record_request("/api/workspace", 150.0, 70, 0.0015)

        summary = await dashboard.get_summary()

        assert summary["total_requests"] == 3
        assert len(summary["endpoints"]) == 2
        assert "/api/qa" in summary["endpoints"]
        assert "/api/workspace" in summary["endpoints"]

    @pytest.mark.asyncio
    async def test_get_summary_includes_timestamp(self):
        """Test that summary includes generation timestamp."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/test", 100.0)

        summary = await dashboard.get_summary()

        assert "generated_at" in summary
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(summary["generated_at"])

    def test_percentile_calculation_empty(self):
        """Test percentile calculation with empty list."""
        result = RealtimeDashboard._percentile([], 50)

        assert result == 0.0

    def test_percentile_calculation_single_value(self):
        """Test percentile calculation with single value."""
        result = RealtimeDashboard._percentile([42.0], 50)

        assert result == 42.0

    def test_percentile_calculation_p50(self):
        """Test p50 calculation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = RealtimeDashboard._percentile(values, 50)

        assert result == 3.0

    def test_percentile_calculation_p90(self):
        """Test p90 calculation."""
        values = list(range(1, 101))  # 1 to 100
        result = RealtimeDashboard._percentile([float(v) for v in values], 90)

        # Allow for index calculation differences
        assert 89.0 <= result <= 91.0

    def test_percentile_calculation_p99(self):
        """Test p99 calculation."""
        values = list(range(1, 101))
        result = RealtimeDashboard._percentile([float(v) for v in values], 99)

        # Allow for index calculation differences
        assert 98.0 <= result <= 100.0

    @pytest.mark.asyncio
    async def test_cache_hit_rate_zero_requests(self):
        """Test cache hit rate with zero requests."""
        dashboard = RealtimeDashboard()

        summary = await dashboard.get_summary()

        # No endpoints, so no cache hit rate to check
        assert summary["endpoints"] == {}

    @pytest.mark.asyncio
    async def test_cache_hit_rate_all_misses(self):
        """Test cache hit rate with all cache misses."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/test", 100.0, cache_hit=False)
        await dashboard.record_request("/api/test", 100.0, cache_hit=False)

        summary = await dashboard.get_summary()
        stats = summary["endpoints"]["/api/test"]

        assert stats["cache_hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_cache_hit_rate_all_hits(self):
        """Test cache hit rate with all cache hits."""
        dashboard = RealtimeDashboard()

        await dashboard.record_request("/api/test", 100.0, cache_hit=True)
        await dashboard.record_request("/api/test", 100.0, cache_hit=True)

        summary = await dashboard.get_summary()
        stats = summary["endpoints"]["/api/test"]

        assert stats["cache_hit_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_concurrent_record_requests(self):
        """Test concurrent request recording."""
        dashboard = RealtimeDashboard()

        # Record multiple requests concurrently
        tasks = [
            dashboard.record_request(f"/api/endpoint{i}", 100.0 + i)
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        summary = await dashboard.get_summary()

        assert summary["total_requests"] == 10
        assert len(summary["endpoints"]) == 10


class TestGetDashboard:
    """Tests for get_dashboard function."""

    def test_get_dashboard_returns_instance(self):
        """Test that get_dashboard returns a RealtimeDashboard instance."""
        dashboard = get_dashboard()

        assert isinstance(dashboard, RealtimeDashboard)

    def test_get_dashboard_singleton(self):
        """Test that get_dashboard returns the same instance."""
        dashboard1 = get_dashboard()
        dashboard2 = get_dashboard()

        assert dashboard1 is dashboard2

    @pytest.mark.asyncio
    async def test_get_dashboard_persistence(self):
        """Test that dashboard state persists across get_dashboard calls."""
        dashboard1 = get_dashboard()
        await dashboard1.record_request("/api/test", 100.0)

        dashboard2 = get_dashboard()
        summary = await dashboard2.get_summary()

        # Should have the metric from dashboard1
        assert summary["total_requests"] == 1
