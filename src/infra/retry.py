"""재시도 로직 및 데코레이터."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def async_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """비동기 함수용 재시도 데코레이터.

    Args:
        max_attempts: 최대 시도 횟수
        min_wait: 최소 대기 시간 (초)
        max_wait: 최대 대기 시간 (초)
        retry_on: 재시도할 예외 타입들

    Example:
        @async_retry(max_attempts=3, retry_on=(RetryableError,))
        async def my_function():
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(retry_on),
                reraise=True,
            ):
                with attempt:
                    logger.debug(
                        "Attempting %s (attempt %d/%d)",
                        func.__name__,
                        attempt.retry_state.attempt_number,
                        max_attempts,
                    )
                    return await func(*args, **kwargs)

        return wrapper

    return decorator


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs: Any,
) -> Any:
    """백오프를 사용한 재시도 유틸리티 함수.

    Args:
        func: 실행할 비동기 함수
        *args: ``func``에 전달할 위치 인자들
        max_attempts: 최대 시도 횟수
        initial_delay: 초기 지연 시간 (초)
        backoff_factor: 백오프 배수
        **kwargs: ``func``에 전달할 키워드 인자들

    Returns:
        함수 실행 결과

    Raises:
        마지막 시도에서 발생한 예외
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(
                "Executing %s (attempt %d/%d)", func.__name__, attempt, max_attempts,
            )
            return await func(*args, **kwargs)
        except Exception as e:  # noqa: PERF203
            last_exception = e
            if attempt < max_attempts:
                logger.warning(
                    "%s failed on attempt %d/%d: %s. Retrying in %.1fs...",
                    func.__name__,
                    attempt,
                    max_attempts,
                    str(e),
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    func.__name__,
                    max_attempts,
                    str(e),
                )

    if last_exception:
        raise last_exception
