"""Rate Limiting 및 동시성 제어 모듈."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from src.constants import DEFAULT_RPM_LIMIT, DEFAULT_RPM_WINDOW_SECONDS

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter


class RateLimitManager:
    """API 호출 Rate Limiting 관리."""

    def __init__(self, max_concurrency: int = 5):
        self.logger = logging.getLogger(__name__)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_limiter: Optional["AsyncLimiter"] = None
        self._init_rate_limiter()

    def _init_rate_limiter(self) -> None:
        """Rate limiter 초기화 (aiolimiter 선택적 의존성)."""
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
        return self._semaphore

    @semaphore.setter
    def semaphore(self, value: asyncio.Semaphore) -> None:
        self._semaphore = value

    @property
    def limiter(self) -> Optional["AsyncLimiter"]:
        return self._rate_limiter

    @limiter.setter
    def limiter(self, value: Optional["AsyncLimiter"]) -> None:
        self._rate_limiter = value
