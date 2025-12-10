"""Rate limiting utilities using aiolimiter.

Provides request rate limiting for API endpoints to prevent abuse.
Uses the existing aiolimiter package for async rate limiting.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from aiolimiter import AsyncLimiter
from fastapi import Request

# Default rate limits (requests per second)
DEFAULT_RATE_LIMIT = 10.0  # 10 requests per second
BURST_SIZE = 20  # Allow burst of 20 requests

# Shared limiters for different endpoint categories
_limiters: dict[str, AsyncLimiter] = {}


def get_limiter(
    name: str, rate: float = DEFAULT_RATE_LIMIT, burst: int = BURST_SIZE
) -> AsyncLimiter:
    """Get or create a named rate limiter.

    Args:
        name: Limiter identifier (e.g., "qa_generate", "workspace")
        rate: Maximum requests per second
        burst: Maximum burst size

    Returns:
        AsyncLimiter instance
    """
    if name not in _limiters:
        _limiters[name] = AsyncLimiter(rate, burst)
    return _limiters[name]


P = ParamSpec("P")
R = TypeVar("R")


def rate_limit(
    name: str,
    rate: float = DEFAULT_RATE_LIMIT,
    burst: int = BURST_SIZE,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]],
    Callable[P, Coroutine[Any, Any, R]],
]:
    """Decorator to apply rate limiting to an async endpoint.

    Usage:
        @router.post("/api/generate")
        @rate_limit("qa_generate", rate=5.0, burst=10)
        async def generate_qa(...): ...

    Args:
        name: Limiter identifier
        rate: Maximum requests per second
        burst: Maximum burst size

    Note:
        Rate limiting is enforced by waiting for the limiter.
        If the wait takes longer than expected, it still proceeds
        (leaky bucket algorithm).
    """
    limiter = get_limiter(name, rate, burst)

    def decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # AsyncLimiter.acquire() is a context manager that blocks until rate allows
            async with limiter:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


async def check_rate_limit(
    request: Request,
    name: str = "default",
    rate: float = DEFAULT_RATE_LIMIT,
    burst: int = BURST_SIZE,
) -> None:
    """Rate limit dependency for endpoints.

    Usage:
        from functools import partial

        @router.post("/api/generate")
        async def generate_qa(
            _: None = Depends(partial(check_rate_limit, name="qa_generate")),
        ): ...

    Args:
        request: FastAPI request object (unused, but required for Depends signature)
        name: Limiter identifier
        rate: Maximum requests per second
        burst: Maximum burst size

    Note:
        This uses a leaky bucket algorithm which blocks until the rate allows.
        For immediate rejection semantics, consider implementing a token bucket
        with try_acquire pattern.
    """
    _ = request  # Unused but required for Depends signature
    limiter = get_limiter(name, rate, burst)
    # Wait until rate limit allows (leaky bucket - may block briefly)
    await limiter.acquire()


__all__ = [
    "BURST_SIZE",
    "DEFAULT_RATE_LIMIT",
    "check_rate_limit",
    "get_limiter",
    "rate_limit",
]
