"""Lightweight metrics utilities for structured latency logging."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def _safe_extra(
    get_extra: Callable[[tuple[Any, ...], dict[str, Any], R | None, bool, float], dict[str, Any]] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: R | None,
    success: bool,
    elapsed_ms: float,
) -> dict[str, Any]:
    """Safely compute extra log fields, swallowing any errors."""
    if get_extra is None:
        return {}
    try:
        return get_extra(args, kwargs, result, success, elapsed_ms) or {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("measure_latency extra builder failed: %s", exc)
        return {}


def measure_latency(
    operation: str,
    *,
    get_extra: Callable[[tuple[Any, ...], dict[str, Any], R | None, bool, float], dict[str, Any]] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Measure and log latency for synchronous callables."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            success = False
            result: R | None = None
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                elapsed_ms = max((time.perf_counter() - start) * 1000, 0.001)
                extra_fields = _safe_extra(
                    get_extra, args, kwargs, result, success, elapsed_ms,
                )
                logger.info(
                    "Operation completed",
                    extra={
                        "metric": "latency",
                        "operation": operation,
                        "duration_ms": elapsed_ms,
                        "success": success,
                        **extra_fields,
                    },
                )

        return wrapper

    return decorator


def measure_latency_async(
    operation: str,
    *,
    get_extra: Callable[[tuple[Any, ...], dict[str, Any], R | None, bool, float], dict[str, Any]] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Measure and log latency for async callables."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            success = False
            result: R | None = None
            try:
                awaitable = func(*args, **kwargs)
                result = await awaitable
                success = True
                return result
            finally:
                elapsed_ms = max((time.perf_counter() - start) * 1000, 0.001)
                extra_fields = _safe_extra(
                    get_extra, args, kwargs, result, success, elapsed_ms,
                )
                logger.info(
                    "Operation completed",
                    extra={
                        "metric": "latency",
                        "operation": operation,
                        "duration_ms": elapsed_ms,
                        "success": success,
                        **extra_fields,
                    },
                )

        return wrapper

    return decorator


__all__ = ["measure_latency", "measure_latency_async"]
