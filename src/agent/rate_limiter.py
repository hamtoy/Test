# -*- coding: utf-8 -*-
"""Rate limiting and concurrency control module.

Provides the new ``RateLimiter`` class and a backwards‑compatible ``RateLimitManager``
wrapper so existing imports continue to work.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from src.constants import DEFAULT_RPM_LIMIT, DEFAULT_RPM_WINDOW_SECONDS

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter


class RateLimiter:
    """Modern rate‑limiter implementation.

    Uses ``aiolimiter.AsyncLimiter`` when available and falls back to a simple
    semaphore otherwise.
    """

    def __init__(self, max_concurrency: int = 5) -> None:
        self.logger = logging.getLogger("GeminiWorkflow")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_limiter: Optional["AsyncLimiter"] = None
        self._init_rate_limiter()

    def _init_rate_limiter(self) -> None:
        try:
            from aiolimiter import AsyncLimiter

            self._rate_limiter = AsyncLimiter(
                max_rate=DEFAULT_RPM_LIMIT, time_period=DEFAULT_RPM_WINDOW_SECONDS
            )
            self.logger.info(
                "Rate limiter enabled: %s requests/%s seconds",
                DEFAULT_RPM_LIMIT,
                DEFAULT_RPM_WINDOW_SECONDS,
            )
        except ImportError:
            self._rate_limiter = None
            self.logger.warning("aiolimiter not installed. Rate limiting disabled.")

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Expose the underlying semaphore for direct manipulation."""
        return self._semaphore

    @semaphore.setter
    def semaphore(self, value: asyncio.Semaphore) -> None:
        self._semaphore = value

    @property
    def limiter(self) -> Optional["AsyncLimiter"]:
        """The optional ``AsyncLimiter`` instance (may be ``None``)."""
        return self._rate_limiter

    @limiter.setter
    def limiter(self, value: Optional["AsyncLimiter"]) -> None:
        self._rate_limiter = value

    async def acquire(self) -> None:
        """Acquire both the rate limiter (if present) and the semaphore."""
        if self._rate_limiter:
            await self._rate_limiter.acquire()
        await self._semaphore.acquire()

    def release(self) -> None:
        """Release the semaphore. ``AsyncLimiter`` does not require release."""
        self._semaphore.release()


# Backwards‑compatible wrapper – retains the original class name used in older code.
class RateLimitManager(RateLimiter):
    """Alias for ``RateLimiter`` to preserve the historic ``RateLimitManager`` API.

    The original implementation exposed the same public methods, so inheriting
    from ``RateLimiter`` provides identical behaviour while keeping import paths
    stable.
    """

    # No additional behaviour – all functionality is provided by ``RateLimiter``.
    pass
