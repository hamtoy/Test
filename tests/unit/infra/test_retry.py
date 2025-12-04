"""Retry logic tests."""
import pytest
from unittest.mock import AsyncMock

from src.infra.retry import async_retry, retry_with_backoff


@pytest.mark.asyncio
async def test_async_retry_succeeds_on_first_attempt():
    """첫 시도에서 성공하는 경우."""
    mock_func = AsyncMock(return_value="success")
    decorated = async_retry(max_attempts=3)(mock_func)

    result = await decorated()

    assert result == "success"
    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_async_retry_succeeds_on_second_attempt():
    """두 번째 시도에서 성공하는 경우."""
    mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])
    decorated = async_retry(max_attempts=3, min_wait=0.1, max_wait=0.2)(mock_func)

    result = await decorated()

    assert result == "success"
    assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_async_retry_fails_after_max_attempts():
    """최대 시도 횟수 초과 시 실패."""
    mock_func = AsyncMock(side_effect=Exception("always fails"))
    decorated = async_retry(max_attempts=3, min_wait=0.1, max_wait=0.2)(mock_func)

    with pytest.raises(Exception, match="always fails"):
        await decorated()

    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_async_retry_only_retries_specified_exceptions():
    """지정된 예외만 재시도."""

    class RetryableError(Exception):
        pass

    class NonRetryableError(Exception):
        pass

    mock_func = AsyncMock(side_effect=NonRetryableError("fail"))
    decorated = async_retry(max_attempts=3, retry_on=(RetryableError,))(mock_func)

    with pytest.raises(NonRetryableError):
        await decorated()

    # 재시도 불가능한 예외이므로 한 번만 호출되어야 함
    assert mock_func.call_count == 1


@pytest.mark.asyncio
async def test_retry_with_backoff_success():
    """retry_with_backoff 성공 테스트."""

    async def success_func():
        return "success"

    result = await retry_with_backoff(success_func, max_attempts=3)
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_with_backoff_eventual_success():
    """retry_with_backoff 재시도 후 성공."""
    call_count = 0

    async def eventually_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("fail")
        return "success"

    result = await retry_with_backoff(
        eventually_succeeds, max_attempts=3, initial_delay=0.1, backoff_factor=2.0
    )
    assert result == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_with_backoff_max_attempts_exceeded():
    """retry_with_backoff 최대 시도 초과."""

    async def always_fails():
        raise Exception("always fails")

    with pytest.raises(Exception, match="always fails"):
        await retry_with_backoff(
            always_fails, max_attempts=3, initial_delay=0.1, backoff_factor=2.0
        )
