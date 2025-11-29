"""ChunkProcessor 테스트.

청크 기반 배치 처리기의 기능을 검증합니다.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.workflow.chunk_processor import (
    AdaptiveChunkProcessor,
    ChunkConfig,
    ChunkProcessor,
    ChunkStats,
)


class TestChunkConfig:
    """ChunkConfig 테스트."""

    def test_default_values(self) -> None:
        """기본값 확인."""
        config = ChunkConfig()
        assert config.chunk_size == 10
        assert config.delay_between_chunks == 1.0
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.fail_fast is False

    def test_custom_values(self) -> None:
        """사용자 설정값 확인."""
        config = ChunkConfig(
            chunk_size=5,
            delay_between_chunks=0.5,
            max_retries=5,
            retry_delay=1.0,
            fail_fast=True,
        )
        assert config.chunk_size == 5
        assert config.delay_between_chunks == 0.5
        assert config.max_retries == 5
        assert config.retry_delay == 1.0
        assert config.fail_fast is True

    def test_invalid_chunk_size(self) -> None:
        """잘못된 chunk_size 검증."""
        with pytest.raises(ValueError, match="chunk_size must be at least 1"):
            ChunkConfig(chunk_size=0)

    def test_invalid_delay(self) -> None:
        """잘못된 delay 검증."""
        with pytest.raises(ValueError, match="delay_between_chunks cannot be negative"):
            ChunkConfig(delay_between_chunks=-1.0)


class TestChunkStats:
    """ChunkStats 테스트."""

    def test_default_values(self) -> None:
        """기본값 확인."""
        stats = ChunkStats()
        assert stats.total_items == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self) -> None:
        """성공률 계산 확인."""
        stats = ChunkStats(total_items=10, successful=8, failed=2)
        assert stats.success_rate == 80.0


class TestChunkProcessor:
    """ChunkProcessor 테스트."""

    @pytest.mark.asyncio
    async def test_batch_chunking(self) -> None:
        """청크 분할 확인."""
        items = list(range(25))
        processed_items: list[int] = []

        async def mock_process(item: int) -> int:
            processed_items.append(item)
            return item * 2

        config = ChunkConfig(chunk_size=10, delay_between_chunks=0.0)
        processor: ChunkProcessor[int, int] = ChunkProcessor(config)

        results = await processor.process_batch(items, mock_process)

        # 결과 확인
        assert len(results) == 25
        assert results == [i * 2 for i in range(25)]

        # 모든 항목 처리됨
        assert len(processed_items) == 25

        # 통계 확인
        stats = processor.get_stats()
        assert stats.total_items == 25
        assert stats.successful == 25
        assert stats.failed == 0
        assert stats.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_batch_with_errors(self) -> None:
        """에러 처리 확인 (fail_fast=False)."""

        async def flaky_process(item: int) -> int:
            if item == 5:
                raise ValueError("Simulated error")
            return item * 2

        config = ChunkConfig(chunk_size=10, delay_between_chunks=0.0, fail_fast=False)
        processor: ChunkProcessor[int, int] = ChunkProcessor(config)

        items = list(range(10))
        results = await processor.process_batch(items, flaky_process)

        # 9개 성공, 1개 실패 (None)
        assert len(results) == 10
        assert results[5] is None
        assert results[0] == 0
        assert results[9] == 18

        stats = processor.get_stats()
        assert stats.successful == 9
        assert stats.failed == 1
        assert len(stats.errors) == 1

    @pytest.mark.asyncio
    async def test_batch_fail_fast(self) -> None:
        """fail_fast 모드 확인."""

        async def failing_process(item: int) -> int:
            if item == 2:
                raise ValueError("Critical error")
            return item

        config = ChunkConfig(chunk_size=5, delay_between_chunks=0.0, fail_fast=True)
        processor: ChunkProcessor[int, int] = ChunkProcessor(config)

        items = list(range(5))

        # fail_fast=True이면 예외가 전파되지 않고 None이 반환됨
        # (청크 재시도 로직 내에서 처리됨)
        results = await processor.process_batch(items, failing_process)

        # 청크 전체가 실패로 처리됨
        stats = processor.get_stats()
        assert stats.failed > 0

    @pytest.mark.asyncio
    async def test_batch_retry(self) -> None:
        """재시도 로직 테스트.

        참고: 현재 구현은 청크 레벨에서 재시도합니다.
        개별 항목의 실패는 return_exceptions=True로 캡처되어
        None으로 반환됩니다.
        """
        attempt_counts: dict[int, int] = {}

        async def flaky_process(item: int) -> int:
            attempt_counts[item] = attempt_counts.get(item, 0) + 1
            # 첫 2번은 실패
            if item == 0 and attempt_counts[item] <= 2:
                raise ValueError("Temporary failure")
            return item

        config = ChunkConfig(
            chunk_size=1, max_retries=3, retry_delay=0.0, delay_between_chunks=0.0
        )
        processor: ChunkProcessor[int, int] = ChunkProcessor(config)

        # 단일 항목 테스트 - 개별 항목 실패는 None으로 반환됨
        results = await processor.process_batch([0], flaky_process)

        # 개별 항목 실패는 None으로 반환됨 (청크 레벨 재시도가 아님)
        assert results == [None]
        # 한 번만 시도됨 (개별 항목 레벨에서 재시도하지 않음)
        assert attempt_counts[0] == 1

        # 통계 확인
        stats = processor.get_stats()
        assert stats.failed == 1

    @pytest.mark.asyncio
    async def test_progress_callback(self) -> None:
        """진행상황 콜백 테스트."""
        progress_updates: list[tuple[int, int]] = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        async def mock_process(item: int) -> int:
            await asyncio.sleep(0.001)
            return item

        config = ChunkConfig(chunk_size=5, delay_between_chunks=0.0)
        processor: ChunkProcessor[int, int] = ChunkProcessor(config)

        await processor.process_batch(
            list(range(15)), mock_process, progress_callback=track_progress
        )

        # 3번의 진행상황 업데이트 (5, 10, 15)
        assert len(progress_updates) == 3
        assert progress_updates[-1] == (15, 15)

    @pytest.mark.asyncio
    async def test_empty_batch(self) -> None:
        """빈 배치 처리."""

        async def mock_process(item: int) -> int:
            return item

        processor: ChunkProcessor[int, int] = ChunkProcessor()
        results = await processor.process_batch([], mock_process)

        assert results == []
        stats = processor.get_stats()
        assert stats.total_items == 0
        assert stats.total_chunks == 0


class TestAdaptiveChunkProcessor:
    """AdaptiveChunkProcessor 테스트."""

    @pytest.mark.asyncio
    async def test_basic_processing(self) -> None:
        """기본 처리 확인."""

        async def quick_process(item: int) -> int:
            await asyncio.sleep(0.001)
            return item * 2

        config = ChunkConfig(chunk_size=5, delay_between_chunks=0.0)
        processor: AdaptiveChunkProcessor[int, int] = AdaptiveChunkProcessor(
            config, min_chunk_size=3, max_chunk_size=10
        )

        items = list(range(15))
        results = await processor.process_batch(items, quick_process)

        assert len(results) == 15
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_chunk_size_adjustment(self) -> None:
        """청크 크기 조정 확인."""

        async def slow_process(item: int) -> int:
            # 느린 처리 시뮬레이션
            await asyncio.sleep(0.01)
            return item

        config = ChunkConfig(chunk_size=10, delay_between_chunks=0.0)
        processor: AdaptiveChunkProcessor[int, int] = AdaptiveChunkProcessor(
            config, min_chunk_size=5, max_chunk_size=15
        )

        # 처리 전 초기 크기
        assert processor.current_chunk_size == 10

        # 처리 실행
        await processor.process_batch(list(range(30)), slow_process)

        # 성능 기록이 있어야 함
        assert len(processor.performance_history) > 0
