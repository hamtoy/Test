"""Tests for SmartBatchProcessor."""

import asyncio

import pytest

from src.agent.batch_processor import SmartBatchProcessor


@pytest.mark.asyncio
async def test_batch_processor_success() -> None:
    processor = SmartBatchProcessor[int, int](max_concurrent=2)

    async def double(x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

    result = await processor.process_batch([1, 2, 3], double)
    assert result.successful == [2, 4, 6]
    assert result.failed == []
    assert result.success_rate == 1.0
    assert result.total == 3


@pytest.mark.asyncio
async def test_batch_processor_partial_failure() -> None:
    processor = SmartBatchProcessor[int, int](max_retries=1)

    async def failing(x: int) -> int:
        if x == 2:
            raise ValueError("fail")
        return x

    result = await processor.process_batch([1, 2, 3], failing)
    assert len(result.failed) == 1
    assert result.success_rate == pytest.approx(2 / 3)
    assert 2 in [item for item, _ in result.failed]


@pytest.mark.asyncio
async def test_batch_processor_respects_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # force rate limiter to sleep on second call
    processor = SmartBatchProcessor[int, int](max_concurrent=2, requests_per_minute=60)
    calls: list[float] = []

    async def record(x: int) -> int:
        calls.append(asyncio.get_event_loop().time())
        return x

    result = await processor.process_batch([1, 2], record)
    assert len(result.successful) == 2
    assert result.success_rate == 1.0
    assert len(calls) == 2
