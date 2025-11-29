"""배치 청크 분할 처리기.

대량 작업을 청크로 나눠 안전하게 처리합니다.
Rate limit 준수 및 메모리 사용 최적화를 제공합니다.

사용 예시:
    from src.workflow.chunk_processor import ChunkProcessor, ChunkConfig

    config = ChunkConfig(chunk_size=10, delay_between_chunks=2.0)
    processor = ChunkProcessor(config)

    results = await processor.process_batch(
        items=queries,
        process_fn=process_single_query,
        progress_callback=on_progress
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")  # 입력 타입
R = TypeVar("R")  # 결과 타입


@dataclass
class ChunkConfig:
    """청크 처리 설정.

    Attributes:
        chunk_size: 청크당 항목 수
        delay_between_chunks: 청크 간 대기 시간 (초)
        max_retries: 실패 시 재시도 횟수
        retry_delay: 재시도 대기 시간 (초)
        fail_fast: 실패 시 즉시 중단 여부
    """

    chunk_size: int = 10
    delay_between_chunks: float = 1.0
    max_retries: int = 3
    retry_delay: float = 2.0
    fail_fast: bool = False

    def __post_init__(self) -> None:
        """설정값 유효성 검사."""
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        if self.delay_between_chunks < 0:
            raise ValueError("delay_between_chunks cannot be negative")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")


@dataclass
class ChunkStats:
    """청크 처리 통계.

    Attributes:
        total_items: 전체 항목 수
        successful: 성공한 항목 수
        failed: 실패한 항목 수
        chunks_processed: 처리된 청크 수
        total_chunks: 전체 청크 수
        duration_seconds: 처리 시간 (초)
        errors: 에러 목록
    """

    total_items: int = 0
    successful: int = 0
    failed: int = 0
    chunks_processed: int = 0
    total_chunks: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """성공률 계산."""
        if self.total_items == 0:
            return 0.0
        return (self.successful / self.total_items) * 100


class ChunkProcessor(Generic[T, R]):
    """청크 기반 배치 처리기.

    대량의 항목을 청크로 나누어 처리하며,
    Rate limit 준수 및 재시도 로직을 제공합니다.
    """

    def __init__(self, config: ChunkConfig | None = None) -> None:
        """ChunkProcessor 초기화.

        Args:
            config: 청크 처리 설정
        """
        self.config = config or ChunkConfig()
        self.stats = ChunkStats()

    async def process_batch(
        self,
        items: list[T],
        process_fn: Callable[[T], Awaitable[R]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[R | None]:
        """배치 처리 실행.

        Args:
            items: 처리할 항목 리스트
            process_fn: 각 항목을 처리하는 비동기 함수
            progress_callback: 진행상황 콜백 (current, total)

        Returns:
            처리 결과 리스트 (실패한 항목은 None)
        """
        results: list[R | None] = []
        total_items = len(items)
        chunk_size = self.config.chunk_size
        total_chunks = (total_items + chunk_size - 1) // chunk_size

        self.stats = ChunkStats(
            total_items=total_items,
            total_chunks=total_chunks,
        )

        logger.info(
            "Starting batch processing: %d items in %d chunks",
            total_items,
            total_chunks,
        )

        start_time = time.time()

        for chunk_idx in range(0, total_items, chunk_size):
            chunk = items[chunk_idx : chunk_idx + chunk_size]
            chunk_num = (chunk_idx // chunk_size) + 1

            logger.info(
                "Processing chunk %d/%d (%d items)",
                chunk_num,
                total_chunks,
                len(chunk),
            )

            # 청크 처리 (재시도 로직 포함)
            chunk_results = await self._process_chunk_with_retry(
                chunk,
                process_fn,
                chunk_num,
            )

            results.extend(chunk_results)
            self.stats.chunks_processed = chunk_num

            # 진행상황 콜백
            if progress_callback:
                progress_callback(len(results), total_items)

            # 다음 청크 전 대기 (마지막 청크는 제외)
            if chunk_idx + chunk_size < total_items:
                logger.debug(
                    "Waiting %.1fs before next chunk...",
                    self.config.delay_between_chunks,
                )
                await asyncio.sleep(self.config.delay_between_chunks)

        self.stats.duration_seconds = time.time() - start_time

        logger.info(
            "Batch processing completed: %d/%d succeeded in %.1fs",
            self.stats.successful,
            total_items,
            self.stats.duration_seconds,
        )

        return results

    async def _process_chunk_with_retry(
        self,
        chunk: list[T],
        process_fn: Callable[[T], Awaitable[R]],
        chunk_num: int,
    ) -> list[R | None]:
        """청크 처리 (재시도 로직 포함).

        Args:
            chunk: 처리할 청크
            process_fn: 처리 함수
            chunk_num: 청크 번호

        Returns:
            처리 결과 리스트
        """
        for attempt in range(self.config.max_retries):
            try:
                # 병렬 처리
                chunk_results_raw = await asyncio.gather(
                    *[process_fn(item) for item in chunk],
                    return_exceptions=True,
                )

                # 예외 처리
                results: list[R | None] = []
                errors: list[tuple[int, BaseException]] = []

                for i, result in enumerate(chunk_results_raw):
                    if isinstance(result, BaseException):
                        errors.append((i, result))

                        if self.config.fail_fast:
                            raise result

                        results.append(None)
                        self.stats.failed += 1
                    else:
                        # result is R (not BaseException)
                        results.append(result)
                        self.stats.successful += 1

                # 에러 로깅
                if errors:
                    logger.warning("Chunk %d had %d errors", chunk_num, len(errors))
                    for idx, error in errors:
                        error_msg = f"Chunk {chunk_num} item {idx}: {type(error).__name__}: {error}"
                        logger.error("  %s", error_msg)
                        self.stats.errors.append(error_msg)

                return results

            except Exception as e:
                logger.error(
                    "Chunk %d failed (attempt %d/%d): %s",
                    chunk_num,
                    attempt + 1,
                    self.config.max_retries,
                    e,
                )

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    # 모든 재시도 실패 - 전체 청크를 실패로 처리
                    self.stats.failed += len(chunk)
                    return [None] * len(chunk)

        # 이론적으로 여기에 도달할 수 없음 (max_retries가 0일 때를 위한 안전장치)
        self.stats.failed += len(chunk)
        return [None] * len(chunk)

    def get_stats(self) -> ChunkStats:
        """처리 통계 반환."""
        return self.stats


class AdaptiveChunkProcessor(ChunkProcessor[T, R]):
    """적응형 청크 처리기.

    성능에 따라 청크 크기를 자동으로 조정합니다.
    """

    def __init__(
        self,
        config: ChunkConfig | None = None,
        min_chunk_size: int = 5,
        max_chunk_size: int = 20,
    ) -> None:
        """AdaptiveChunkProcessor 초기화.

        Args:
            config: 기본 청크 설정
            min_chunk_size: 최소 청크 크기
            max_chunk_size: 최대 청크 크기
        """
        super().__init__(config)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.current_chunk_size = self.config.chunk_size
        self.performance_history: list[float] = []

    async def process_batch(
        self,
        items: list[T],
        process_fn: Callable[[T], Awaitable[R]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[R | None]:
        """적응형 배치 처리 실행.

        Args:
            items: 처리할 항목 리스트
            process_fn: 처리 함수
            progress_callback: 진행상황 콜백

        Returns:
            처리 결과 리스트
        """
        results: list[R | None] = []
        total_items = len(items)
        idx = 0

        self.stats = ChunkStats(total_items=total_items)

        start_time = time.time()
        chunk_num = 0

        while idx < total_items:
            chunk = items[idx : idx + self.current_chunk_size]
            chunk_num += 1

            # 청크 처리 시간 측정
            chunk_start = time.time()
            chunk_results = await self._process_chunk_with_retry(
                chunk,
                process_fn,
                chunk_num,
            )
            chunk_duration = time.time() - chunk_start

            results.extend(chunk_results)

            # 성능 기록
            avg_time_per_item = chunk_duration / len(chunk) if chunk else 0
            self.performance_history.append(avg_time_per_item)

            # 청크 크기 조정
            self._adjust_chunk_size(avg_time_per_item)

            idx += len(chunk)

            if progress_callback:
                progress_callback(len(results), total_items)

            # 다음 청크 전 대기
            if idx < total_items:
                await asyncio.sleep(self.config.delay_between_chunks)

        self.stats.duration_seconds = time.time() - start_time
        self.stats.total_chunks = chunk_num
        self.stats.chunks_processed = chunk_num

        return results

    def _adjust_chunk_size(self, avg_time: float) -> None:
        """성능 기반 청크 크기 조정.

        Args:
            avg_time: 항목당 평균 처리 시간
        """
        # 너무 느리면 청크 줄이기
        if avg_time > 2.0 and self.current_chunk_size > self.min_chunk_size:
            old_size = self.current_chunk_size
            self.current_chunk_size = max(
                self.min_chunk_size, self.current_chunk_size - 2
            )
            logger.info(
                "Chunk size decreased: %d -> %d (avg_time=%.2fs)",
                old_size,
                self.current_chunk_size,
                avg_time,
            )

        # 빠르면 청크 늘리기
        elif avg_time < 0.5 and self.current_chunk_size < self.max_chunk_size:
            old_size = self.current_chunk_size
            self.current_chunk_size = min(
                self.max_chunk_size, self.current_chunk_size + 2
            )
            logger.info(
                "Chunk size increased: %d -> %d (avg_time=%.2fs)",
                old_size,
                self.current_chunk_size,
                avg_time,
            )
