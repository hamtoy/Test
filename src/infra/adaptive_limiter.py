# -*- coding: utf-8 -*-
"""Adaptive Rate Limiter implementing a TCP Vegas-like algorithm.

Dynamically adjusts concurrency based on response latency and errors
to optimize throughput while preventing 429 Too Many Requests errors.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# Polling interval for checking slot availability (seconds)
_POLL_INTERVAL = 0.1


@dataclass
class AdaptiveStats:
    """Statistics for adaptive rate limiting."""

    concurrency: int = 1
    success_count: int = 0
    throttle_count: int = 0
    avg_latency: float = 0.0


class AdaptiveRateLimiter:
    """Adaptive Rate Limiter implementing a TCP Vegas-like algorithm.

    Dynamically adjusts concurrency based on response latency and errors.
    Uses Additive Increase/Multiplicative Decrease (AIMD) approach:
    - Additive Increase: When latency is below target, increase limit linearly
    - Multiplicative Decrease: When errors occur, decrease limit by half

    Args:
        initial_concurrency: Starting concurrency limit (default: 1)
        max_concurrency: Maximum allowed concurrency (default: 10)
        min_concurrency: Minimum allowed concurrency (default: 1)
        target_latency: Target response latency in seconds (default: 2.0)
        window_size: Number of requests before updating limits (default: 10)
    """

    def __init__(
        self,
        initial_concurrency: int = 1,
        max_concurrency: int = 10,
        min_concurrency: int = 1,
        target_latency: float = 2.0,
        window_size: int = 10,
    ) -> None:
        """Initialize the adaptive rate limiter.

        Args:
            initial_concurrency: Starting concurrency level.
            max_concurrency: Maximum allowed concurrency.
            min_concurrency: Minimum allowed concurrency.
            target_latency: Target response latency in seconds.
            window_size: Number of requests before updating limits.
        """
        self._current_limit = float(initial_concurrency)
        self._max_limit = max_concurrency
        self._min_limit = min_concurrency
        self._target_latency = target_latency
        self._window_size = window_size

        self._latencies: list[float] = []
        self._errors = 0
        self._lock = asyncio.Lock()
        self._active_count = 0
        self._condition = asyncio.Condition(self._lock)

        # Statistics
        self.stats = AdaptiveStats()

    @property
    def current_limit(self) -> int:
        """Current concurrency limit."""
        return int(self._current_limit)

    async def _update_limits(self) -> None:
        """Update concurrency limits based on recent performance."""
        if not self._latencies:
            return

        avg_latency = sum(self._latencies) / len(self._latencies)
        self.stats.avg_latency = avg_latency

        # Vegas Algorithm Logic:
        # If latency is below target (fast) -> increase rate
        # If latency is above target (slow) -> decrease rate

        if self._errors > 0:
            # Error occurred: Multiplicative Decrease (halve the limit)
            self._current_limit = max(self._min_limit, self._current_limit * 0.5)
            logger.warning(
                "Throttling: Error detected. Limit reduced to %d", self.current_limit
            )

        elif avg_latency < self._target_latency:
            # Under target latency: Additive Increase
            self._current_limit = min(self._max_limit, self._current_limit + 1)

        else:
            # Above target latency: Additive Decrease
            self._current_limit = max(self._min_limit, self._current_limit - 0.5)

        self.stats.concurrency = self.current_limit

        # Reset window
        self._latencies.clear()
        self._errors = 0

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Acquire permission to send a request.

        Blocks if current concurrency limit is reached.
        Automatically tracks latency and adjusts limits based on performance.

        Yields:
            None: Context manager that tracks request timing

        Raises:
            Exception: Re-raises any exception from the wrapped code
        """
        # Wait until a slot becomes available using condition variable
        async with self._condition:
            while self._active_count >= self.current_limit:
                # Use wait_for with timeout to periodically re-check the dynamic limit
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._condition.wait(), timeout=_POLL_INTERVAL
                    )
            self._active_count += 1

        start_time = time.monotonic()
        error_occurred = False

        try:
            yield
            async with self._lock:
                self.stats.success_count += 1
        except Exception:
            error_occurred = True
            async with self._lock:
                self._errors += 1
                self.stats.throttle_count += 1
            raise
        finally:
            latency = time.monotonic() - start_time

            async with self._condition:
                self._active_count -= 1
                self._latencies.append(latency)
                if len(self._latencies) >= self._window_size or error_occurred:
                    await self._update_limits()
                # Notify waiting coroutines that a slot is available
                self._condition.notify()
