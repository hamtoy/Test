"""성능 메트릭 자동 수집."""

from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime, timedelta


@dataclass
class PerformanceMetric:
    """성능 메트릭 단일 항목."""

    operation: str  # "query_generation", "evaluation", etc.
    duration_ms: float  # 소요 시간 (밀리초)
    tokens_used: int  # 토큰 사용량
    cache_hit: bool  # 캐시 히트 여부
    timestamp: datetime  # 타임스탬프
    status: str  # "success", "retry", "timeout"


@dataclass
class _StatsData:
    """Helper class for collecting stats data."""

    count: int = 0
    durations: list[float] = field(default_factory=list)
    cache_hits: int = 0
    successes: int = 0


class PerformanceTracker:
    """성능 메트릭 추적."""

    def __init__(self, window_minutes: int = 60):
        """Initialize performance tracker.

        Args:
            window_minutes: 메트릭 윈도우 크기 (분 단위)
        """
        self.window = timedelta(minutes=window_minutes)
        self.metrics: list[PerformanceMetric] = []

    def record(self, metric: PerformanceMetric) -> None:
        """메트릭 기록.

        Args:
            metric: 기록할 메트릭 항목
        """
        self.metrics.append(metric)
        self._cleanup_old()

    def get_stats(self, operation: str | None = None) -> Dict[str, Dict[str, float]]:
        """작업별 통계 반환.

        Args:
            operation: 특정 작업 필터 (None이면 전체)

        Returns:
            {
                "query_generation": {
                    "count": 10,
                    "avg_duration_ms": 234.5,
                    "min_duration_ms": 150,
                    "max_duration_ms": 400,
                    "cache_hit_rate": 0.3,
                    "success_rate": 0.9,
                }
            }
        """
        filtered = [
            m for m in self.metrics if not operation or m.operation == operation
        ]

        if not filtered:
            return {}

        result: Dict[str, _StatsData] = {}

        for metric in filtered:
            op = metric.operation
            if op not in result:
                result[op] = _StatsData()
            result[op].count += 1
            result[op].durations.append(metric.duration_ms)
            if metric.cache_hit:
                result[op].cache_hits += 1
            if metric.status == "success":
                result[op].successes += 1

        # 통계 계산
        stats: Dict[str, Dict[str, float]] = {}
        for op, data in result.items():
            durations = data.durations
            if durations:
                stats[op] = {
                    "count": float(data.count),
                    "avg_duration_ms": sum(durations) / len(durations),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "cache_hit_rate": (
                        float(data.cache_hits) / float(data.count)
                        if data.count > 0
                        else 0.0
                    ),
                    "success_rate": (
                        float(data.successes) / float(data.count)
                        if data.count > 0
                        else 0.0
                    ),
                }

        return stats

    def _cleanup_old(self) -> None:
        """윈도우 범위 밖 메트릭 제거."""
        cutoff = datetime.now() - self.window
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff]


# 전역 트래커
_tracker = PerformanceTracker()


def get_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance.

    Returns:
        전역 PerformanceTracker 인스턴스
    """
    return _tracker
