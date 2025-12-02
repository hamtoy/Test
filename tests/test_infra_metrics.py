"""Tests for infra metrics utilities."""

import asyncio
import logging

import pytest

from src.infra.metrics import measure_latency, measure_latency_async


def test_measure_latency_logs_duration(caplog: pytest.LogCaptureFixture) -> None:
    """measure_latency should emit structured info logs."""

    @measure_latency(
        "test_sync",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "extra_field": "value",
            "result_value": result,
        },
    )
    def sample(a: int, b: int) -> int:
        return a + b

    caplog.set_level(logging.INFO)
    assert sample(1, 2) == 3

    record = caplog.records[-1]
    assert record.levelname == "INFO"
    assert record.operation == "test_sync"
    assert record.metric == "latency"
    assert record.duration_ms > 0
    assert record.success is True
    assert record.extra_field == "value"
    assert record.result_value == 3


def test_measure_latency_async_logs_duration(caplog: pytest.LogCaptureFixture) -> None:
    """measure_latency_async should emit structured info logs."""

    @measure_latency_async(
        "test_async",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "extra_async": True,
            "success_flag": success,
        },
    )
    async def sample_async(a: int) -> int:
        await asyncio.sleep(0.001)
        return a * 2

    caplog.set_level(logging.INFO)
    result = asyncio.run(sample_async(5))
    assert result == 10

    record = caplog.records[-1]
    assert record.operation == "test_async"
    assert record.metric == "latency"
    assert record.success is True
    assert record.extra_async is True


def test_measure_latency_failure_logs_success_false(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failure should still log with success=False."""

    @measure_latency("failing_op")
    def boom() -> None:
        raise RuntimeError("fail")

    caplog.set_level(logging.INFO)
    with pytest.raises(RuntimeError):
        boom()

    record = caplog.records[-1]
    assert record.operation == "failing_op"
    assert record.success is False
    assert record.metric == "latency"
