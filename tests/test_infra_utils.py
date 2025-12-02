"""Tests for infrastructure utility helpers."""

import asyncio

import pytest

from src.infra.utils import run_async_safely


class TestRunAsyncSafely:
    """Run coroutines safely from sync contexts."""

    def test_run_async_safely_no_running_loop(self) -> None:
        """Should run when no event loop is active."""

        async def sample_coro() -> str:
            await asyncio.sleep(0.001)
            return "success"

        result = run_async_safely(sample_coro())
        assert result == "success"

    def test_run_async_safely_with_running_loop(self) -> None:
        """Should run when an event loop is already running."""

        async def inner_coro() -> str:
            return "inner_result"

        async def outer_coro() -> str:
            return run_async_safely(inner_coro())

        result = asyncio.run(outer_coro())
        assert result == "inner_result"

    def test_run_async_safely_propagates_exception(self) -> None:
        """Propagate exceptions raised inside the coroutine."""

        async def failing_coro() -> str:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            run_async_safely(failing_coro())
