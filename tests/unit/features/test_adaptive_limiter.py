# -*- coding: utf-8 -*-
"""Tests for the Adaptive Rate Limiter module."""

from __future__ import annotations

import asyncio

import pytest

from src.infra.adaptive_limiter import AdaptiveRateLimiter, AdaptiveStats


class TestAdaptiveStats:
    """Tests for AdaptiveStats dataclass."""

    def test_default_values(self) -> None:
        """Test default values are initialized correctly."""
        stats = AdaptiveStats()
        assert stats.concurrency == 1
        assert stats.success_count == 0
        assert stats.throttle_count == 0
        assert stats.avg_latency == 0.0


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter class."""

    def test_initial_limit(self) -> None:
        """Test initial concurrency limit is set correctly."""
        limiter = AdaptiveRateLimiter(initial_concurrency=5)
        assert limiter.current_limit == 5

    def test_bounds(self) -> None:
        """Test min and max concurrency bounds."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=1,
            max_concurrency=10,
            min_concurrency=2,
        )
        assert limiter._min_limit == 2
        assert limiter._max_limit == 10

    @pytest.mark.asyncio
    async def test_acquire_basic(self) -> None:
        """Test basic acquire functionality."""
        limiter = AdaptiveRateLimiter(initial_concurrency=2)

        async with limiter.acquire():
            pass  # Simple acquire and release

        assert limiter.stats.success_count == 1

    @pytest.mark.asyncio
    async def test_adaptive_scaling_up(self) -> None:
        """Test that concurrency limit increases when latency is low."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=1,
            max_concurrency=5,
            target_latency=0.5,
            window_size=3,
        )

        # Simulate fast responses (below target latency)
        for _ in range(5):
            async with limiter.acquire():
                await asyncio.sleep(0.1)  # Faster than target (0.5)

        assert limiter.current_limit > 1, "Limit should increase when latency is low"

    @pytest.mark.asyncio
    async def test_adaptive_scaling_down_on_error(self) -> None:
        """Test that concurrency limit decreases on error."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=4,
            min_concurrency=1,
            window_size=1,
        )

        with pytest.raises(ValueError):
            async with limiter.acquire():
                raise ValueError("Simulated API Error")

        assert limiter.current_limit < 4, "Limit should decrease on error"
        assert limiter.stats.throttle_count == 1

    @pytest.mark.asyncio
    async def test_scaling_down_on_high_latency(self) -> None:
        """Test that concurrency limit decreases when latency is high."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=3,
            min_concurrency=1,
            target_latency=0.05,  # Very low target
            window_size=2,
        )

        # Simulate slow responses (above target latency)
        for _ in range(3):
            async with limiter.acquire():
                await asyncio.sleep(0.2)  # Slower than target (0.05)

        assert limiter.current_limit < 3, "Limit should decrease when latency is high"

    @pytest.mark.asyncio
    async def test_respects_max_limit(self) -> None:
        """Test that concurrency never exceeds max_concurrency."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=4,
            max_concurrency=5,
            target_latency=1.0,
            window_size=2,
        )

        # Many fast requests
        for _ in range(10):
            async with limiter.acquire():
                await asyncio.sleep(0.01)

        assert limiter.current_limit <= 5, "Limit should not exceed max_concurrency"

    @pytest.mark.asyncio
    async def test_respects_min_limit(self) -> None:
        """Test that concurrency never goes below min_concurrency."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=2,
            min_concurrency=1,
            window_size=1,
        )

        # Multiple errors should not go below min
        for _ in range(3):
            with pytest.raises(RuntimeError):
                async with limiter.acquire():
                    raise RuntimeError("Error")

        assert limiter.current_limit >= 1, "Limit should not go below min_concurrency"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test handling of concurrent requests."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=3,
            max_concurrency=5,
            window_size=5,
        )

        async def make_request() -> None:
            async with limiter.acquire():
                await asyncio.sleep(0.05)

        # Run multiple concurrent requests
        await asyncio.gather(*[make_request() for _ in range(5)])

        assert limiter.stats.success_count == 5

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        """Test that statistics are tracked correctly."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=2,
            window_size=3,
            target_latency=1.0,
        )

        # Successful requests
        for _ in range(2):
            async with limiter.acquire():
                await asyncio.sleep(0.01)

        assert limiter.stats.success_count == 2
        assert limiter.stats.throttle_count == 0

        # Error request
        with pytest.raises(Exception):
            async with limiter.acquire():
                raise Exception("Test error")

        assert limiter.stats.throttle_count == 1

    @pytest.mark.asyncio
    async def test_latency_tracking(self) -> None:
        """Test that average latency is tracked correctly."""
        limiter = AdaptiveRateLimiter(
            initial_concurrency=2,
            window_size=3,
            target_latency=1.0,
        )

        # Make requests with known sleep time
        for _ in range(3):
            async with limiter.acquire():
                await asyncio.sleep(0.1)

        # After window_size requests, avg_latency should be updated
        assert limiter.stats.avg_latency >= 0.1
