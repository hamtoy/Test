"""워크플로우 벤치마크 스크립트.

전체 워크플로우를 10회 실행하여 평균/p50/p99 지연시간을 출력합니다.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time
from typing import Callable, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def calculate_percentile(data: List[float], percentile: float) -> float:
    """백분위수 계산.

    Args:
        data: 정렬된 데이터 리스트
        percentile: 백분위수 (0-100)

    Returns:
        해당 백분위수 값
    """
    if not data:
        return 0.0

    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (percentile / 100)
    f = int(k)
    c = f + 1

    if c >= len(sorted_data):
        return sorted_data[-1]

    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


class BenchmarkRunner:
    """워크플로우 벤치마크 러너."""

    def __init__(self, iterations: int = 10):
        """벤치마크 러너 초기화.

        Args:
            iterations: 실행 횟수 (기본: 10)
        """
        self.iterations = iterations
        self.latencies: List[float] = []

    def run_sync(
        self,
        func: Callable[[], None],
        warmup: int = 1,
    ) -> dict[str, float]:
        """동기 함수 벤치마크 실행.

        Args:
            func: 벤치마크할 동기 함수
            warmup: 워밍업 실행 횟수

        Returns:
            평균, p50, p99 지연시간 딕셔너리
        """
        # Warmup
        for _ in range(warmup):
            func()

        # Benchmark
        self.latencies = []
        for i in range(self.iterations):
            start = time.perf_counter()
            func()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            self.latencies.append(elapsed)
            logger.info("Iteration %d/%d: %.2f ms", i + 1, self.iterations, elapsed)

        return self._calculate_stats()

    async def run_async(
        self,
        coro_func: Callable[[], object],
        warmup: int = 1,
    ) -> dict[str, float]:
        """비동기 함수 벤치마크 실행.

        Args:
            coro_func: 벤치마크할 비동기 함수
            warmup: 워밍업 실행 횟수

        Returns:
            평균, p50, p99 지연시간 딕셔너리
        """
        # Warmup
        for _ in range(warmup):
            await coro_func()  # type: ignore[misc]

        # Benchmark
        self.latencies = []
        for i in range(self.iterations):
            start = time.perf_counter()
            await coro_func()  # type: ignore[misc]
            elapsed = (time.perf_counter() - start) * 1000  # ms
            self.latencies.append(elapsed)
            logger.info("Iteration %d/%d: %.2f ms", i + 1, self.iterations, elapsed)

        return self._calculate_stats()

    def _calculate_stats(self) -> dict[str, float]:
        """통계 계산.

        Returns:
            평균, p50, p99 지연시간 딕셔너리
        """
        if not self.latencies:
            return {"avg": 0.0, "p50": 0.0, "p99": 0.0}

        return {
            "avg": statistics.mean(self.latencies),
            "p50": calculate_percentile(self.latencies, 50),
            "p99": calculate_percentile(self.latencies, 99),
            "min": min(self.latencies),
            "max": max(self.latencies),
            "stdev": statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0,
        }

    def print_results(self, stats: dict[str, float], name: str = "Benchmark") -> None:
        """결과 출력.

        Args:
            stats: 통계 딕셔너리
            name: 벤치마크 이름
        """
        logger.info("=" * 50)
        logger.info("%s Results (%d iterations)", name, self.iterations)
        logger.info("=" * 50)
        logger.info("Average: %.2f ms", stats["avg"])
        logger.info("P50:     %.2f ms", stats["p50"])
        logger.info("P99:     %.2f ms", stats["p99"])
        logger.info("Min:     %.2f ms", stats.get("min", 0))
        logger.info("Max:     %.2f ms", stats.get("max", 0))
        logger.info("Stdev:   %.2f ms", stats.get("stdev", 0))
        logger.info("=" * 50)


def sample_sync_workload() -> None:
    """샘플 동기 워크로드 (데모용)."""
    time.sleep(0.01)  # 10ms 시뮬레이션


async def sample_async_workload() -> None:
    """샘플 비동기 워크로드 (데모용)."""
    await asyncio.sleep(0.01)  # 10ms 시뮬레이션


def main() -> None:
    """메인 함수."""
    parser = argparse.ArgumentParser(description="Workflow Benchmark Tool")
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations (default: 10)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of warmup iterations (default: 1)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with demo workload",
    )
    args = parser.parse_args()

    runner = BenchmarkRunner(iterations=args.iterations)

    if args.demo:
        logger.info("Running demo benchmark...")
        stats = runner.run_sync(sample_sync_workload, warmup=args.warmup)
        runner.print_results(stats, "Demo Sync Workload")

        async def run_async_demo() -> None:
            async_stats = await runner.run_async(
                sample_async_workload, warmup=args.warmup
            )
            runner.print_results(async_stats, "Demo Async Workload")

        asyncio.run(run_async_demo())
    else:
        logger.info("Benchmark runner initialized.")
        logger.info(
            "Use --demo for a sample run, or import BenchmarkRunner in your workflow."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
