"""Prometheus 메트릭 수집

애플리케이션 상태와 성능 메트릭을 Prometheus 형식으로 제공합니다.
"""

from __future__ import annotations

from typing import Dict

# prometheus_client가 없을 경우 스텁 구현 사용
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # 스텁 구현
    class Counter:  # type: ignore[no-redef]
        """Stub Counter implementation when Prometheus is not available."""

        def __init__(self, name: str, doc: str, _labelnames: list[str] | None = None):
            """Initialize the stub counter."""
            self._name = name
            self._values: Dict[tuple[str, ...], float] = {}

        def labels(self, *args: str) -> "Counter":
            """Return self for method chaining."""
            return self

        def inc(self, amount: float = 1) -> None:
            """Increment the counter (no-op in stub)."""
            pass

    class Histogram:  # type: ignore[no-redef]
        """Stub Histogram implementation when Prometheus is not available."""

        def __init__(self, name: str, doc: str, _labelnames: list[str] | None = None):
            """Initialize the stub histogram."""
            self._name = name

        def labels(self, *args: str) -> "Histogram":
            """Return self for method chaining."""
            return self

        def observe(self, amount: float) -> None:
            """Observe a value (no-op in stub)."""
            pass

    class Gauge:  # type: ignore[no-redef]
        """Stub Gauge implementation when Prometheus is not available."""

        def __init__(self, name: str, doc: str, _labelnames: list[str] | None = None):
            """Initialize the stub gauge."""
            self._name = name

        def set(self, value: float) -> None:
            """Set the gauge value (no-op in stub)."""
            self._value = value

        def inc(self, amount: float = 1) -> None:
            """Increment the gauge (no-op in stub)."""
            self._value += amount

        def dec(self, amount: float = 1) -> None:
            """Decrement the gauge (no-op in stub)."""
            self._value -= amount

    def generate_latest() -> bytes:
        """Generate Prometheus metrics output (stub returns placeholder)."""
        return b"# Prometheus client not installed\n"


# =============================================================================
# API 메트릭
# =============================================================================

api_calls_total = Counter(
    "gemini_api_calls_total",
    "Total Gemini API calls",
    ["model", "status"],
)

api_latency = Histogram(
    "gemini_api_latency_seconds",
    "Gemini API latency",
    ["model"],
)

api_errors = Counter(
    "gemini_api_errors_total",
    "Total API errors",
    ["model", "error_type"],
)

# =============================================================================
# 캐시 메트릭
# =============================================================================

cache_hits = Counter(
    "cache_hits_total",
    "Cache hits",
    ["cache_type"],
)

cache_misses = Counter(
    "cache_misses_total",
    "Cache misses",
    ["cache_type"],
)

cache_size = Gauge(
    "cache_size_bytes",
    "Cache size in bytes",
)

# =============================================================================
# 비용 메트릭
# =============================================================================

token_usage = Counter(
    "token_usage_total",
    "Total tokens used",
    ["type"],
)

cost_usd = Counter(
    "cost_usd_total",
    "Total cost in USD",
)

# =============================================================================
# 워크플로우 메트릭
# =============================================================================

workflow_duration = Histogram(
    "workflow_duration_seconds",
    "Workflow duration",
)

workflow_status = Counter(
    "workflow_status_total",
    "Workflow status",
    ["status"],
)

# =============================================================================
# 헬퍼 함수
# =============================================================================


def get_metrics() -> bytes:
    """Prometheus 포맷으로 메트릭 반환

    Returns:
        Prometheus 텍스트 형식의 메트릭 데이터
    """
    result = generate_latest()
    # prometheus_client returns bytes, but we handle str for safety
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        return result.encode("utf-8")
    return b"# Unable to generate metrics\n"


def record_api_call(model: str, status: str, latency_seconds: float) -> None:
    """API 호출 메트릭 기록

    Args:
        model: 사용된 모델명
        status: 호출 상태 (success, error 등)
        latency_seconds: 응답 시간 (초)
    """
    if PROMETHEUS_AVAILABLE:
        api_calls_total.labels(model=model, status=status).inc()
        api_latency.labels(model=model).observe(latency_seconds)


def record_api_error(model: str, error_type: str) -> None:
    """API 에러 메트릭 기록

    Args:
        model: 사용된 모델명
        error_type: 에러 타입
    """
    if PROMETHEUS_AVAILABLE:
        api_errors.labels(model=model, error_type=error_type).inc()


def record_cache_access(cache_type: str, hit: bool) -> None:
    """캐시 접근 메트릭 기록

    Args:
        cache_type: 캐시 타입
        hit: 캐시 히트 여부
    """
    if PROMETHEUS_AVAILABLE:
        if hit:
            cache_hits.labels(cache_type=cache_type).inc()
        else:
            cache_misses.labels(cache_type=cache_type).inc()


def record_token_usage(prompt_tokens: int, completion_tokens: int) -> None:
    """토큰 사용량 메트릭 기록

    Args:
        prompt_tokens: 입력 토큰 수
        completion_tokens: 출력 토큰 수
    """
    if PROMETHEUS_AVAILABLE:
        token_usage.labels(type="prompt").inc(prompt_tokens)
        token_usage.labels(type="completion").inc(completion_tokens)


def record_workflow_completion(status: str, duration_seconds: float) -> None:
    """워크플로우 완료 메트릭 기록

    Args:
        status: 완료 상태
        duration_seconds: 소요 시간 (초)
    """
    if PROMETHEUS_AVAILABLE:
        workflow_status.labels(status=status).inc()
        workflow_duration.observe(duration_seconds)


__all__ = [
    "get_metrics",
    "record_api_call",
    "record_api_error",
    "record_cache_access",
    "record_token_usage",
    "record_workflow_completion",
    "api_calls_total",
    "api_latency",
    "api_errors",
    "cache_hits",
    "cache_misses",
    "cache_size",
    "token_usage",
    "cost_usd",
    "workflow_duration",
    "workflow_status",
    "PROMETHEUS_AVAILABLE",
]
