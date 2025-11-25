"""Rate Limiting 모듈.

API 호출 속도 제한 및 동시성 제어 기능 제공.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from src.constants import DEFAULT_RPM_LIMIT, DEFAULT_RPM_WINDOW_SECONDS

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter


class RateLimiter:
    """API Rate Limiting 및 동시성 제어 클래스.

    AsyncLimiter와 Semaphore를 사용하여 API 호출 빈도를 제어합니다.
    """

    def __init__(self, max_concurrency: int) -> None:
        """RateLimiter 초기화.

        Args:
            max_concurrency: 최대 동시 실행 개수
        """
        self.logger = logging.getLogger("GeminiWorkflow")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_limiter: Optional["AsyncLimiter"] = None

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
        """동시성 제어 세마포어."""
        return self._semaphore

    @property
    def limiter(self) -> Optional["AsyncLimiter"]:
        """Rate limiter 인스턴스 (None if unavailable)."""
        return self._rate_limiter

    @limiter.setter
    def limiter(self, value: Optional["AsyncLimiter"]) -> None:
        """Rate limiter 인스턴스 설정 (테스트용)."""
        self._rate_limiter = value

    async def acquire(self) -> None:
        """Rate limiter와 세마포어 획득.

        Rate limiter가 설정되어 있으면 함께 획득합니다.
        """
        if self._rate_limiter:
            await self._rate_limiter.acquire()
        await self._semaphore.acquire()

    def release(self) -> None:
        """세마포어 해제.

        Note: aiolimiter는 시간 기반이므로 별도 해제 불필요.
        """
        self._semaphore.release()
