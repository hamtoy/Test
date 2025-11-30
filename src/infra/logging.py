import logging
import logging.handlers
import os
import queue
import re
from datetime import datetime
from typing import Any, Tuple

from pythonjsonlogger.json import JsonFormatter
from rich.logging import RichHandler

from src.config.constants import SENSITIVE_PATTERN


def _resolve_log_level(explicit: str | None = None) -> int:
    """Resolve log level from explicit value or LOG_LEVEL env var, defaulting to INFO."""
    base_name = explicit if explicit is not None else os.getenv("LOG_LEVEL", "INFO")
    level_name = base_name.upper()
    level_value = getattr(logging, level_name, logging.INFO)
    return level_value if isinstance(level_value, int) else logging.INFO


class SensitiveDataFilter(logging.Filter):
    """[Security] 로그에서 민감한 정보(API Key 등)를 마스킹하는 필터
    """

    sensitive_regex = re.compile(SENSITIVE_PATTERN)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "AIza" in msg:
            record.msg = self.sensitive_regex.sub("[FILTERED_API_KEY]", msg)

            if record.args:
                new_args: list[object] = []
                for arg in record.args:
                    if isinstance(arg, str):
                        new_args.append(
                            self.sensitive_regex.sub("[FILTERED_API_KEY]", arg)
                        )
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)

        return True


def _build_file_handler(
    log_level: int,
    use_json: bool,
    sensitive_filter: logging.Filter,
    filename: str,
) -> logging.Handler:
    """Create RotatingFileHandler with optional JSON formatting."""
    file_handler = logging.handlers.RotatingFileHandler(
        filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    formatter: logging.Formatter
    if use_json:
        formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)
    return file_handler


def _build_console_handler(
    log_level: int, sensitive_filter: logging.Filter
) -> logging.Handler:
    """Create Rich console handler."""
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
    )
    console_handler.setLevel(log_level)
    console_handler.addFilter(sensitive_filter)
    return console_handler


def setup_logging(
    env: str | None = None, log_level: str | None = None
) -> Tuple[logging.Logger, logging.handlers.QueueListener]:
    """[Non-Blocking Logging] QueueHandler 패턴 + 환경별 포맷/출력 제어

    - production: JSON 포맷, 파일만(회전)
    - local/dev: 텍스트 포맷, 콘솔 + 파일(회전)
    """
    log_env = (env or os.getenv("APP_ENV") or "local").lower()
    is_production = log_env in {"prod", "production"}

    log_queue: queue.Queue[Any] = queue.Queue(-1)  # 무제한 큐
    resolved_level = _resolve_log_level(log_level)
    sensitive_filter = SensitiveDataFilter()

    handlers = []

    info_log = os.getenv("LOG_FILE", "app.log")
    error_log = os.getenv("ERROR_LOG_FILE", "error.log")

    file_handler = _build_file_handler(
        log_level=resolved_level,
        use_json=is_production,
        sensitive_filter=sensitive_filter,
        filename=info_log,
    )
    handlers.append(file_handler)

    error_handler = _build_file_handler(
        log_level=logging.ERROR,
        use_json=is_production,
        sensitive_filter=sensitive_filter,
        filename=error_log,
    )
    handlers.append(error_handler)

    if not is_production:
        handlers.append(_build_console_handler(resolved_level, sensitive_filter))

    listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True,
    )

    queue_handler = logging.handlers.QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    # 기존 핸들러 제거 (중복 방지)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(queue_handler)
    listener.start()

    return logging.getLogger("GeminiWorkflow"), listener


def get_log_level() -> int:
    """환경에 따른 로그 레벨 결정

    Returns:
        로그 레벨 (logging.DEBUG, logging.INFO 등)
    """
    env = os.getenv("ENVIRONMENT", "development")

    level_map = {
        "development": logging.DEBUG,
        "staging": logging.INFO,
        "production": logging.WARNING,
    }

    # LOG_LEVEL_OVERRIDE가 있으면 우선 적용
    override = os.getenv("LOG_LEVEL_OVERRIDE")
    if override:
        level = getattr(logging, override.upper(), None)
        if isinstance(level, int):
            return level

    return level_map.get(env, logging.INFO)


def set_log_level(level: str) -> bool:
    """런타임에 로그 레벨 동적 변경

    Args:
        level: 로그 레벨 문자열 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        성공 시 True, 실패 시 False
    """
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        return False

    new_level = getattr(logging, level.upper())
    logging.getLogger().setLevel(new_level)

    # 모든 핸들러의 레벨도 업데이트
    for handler in logging.getLogger().handlers:
        handler.setLevel(new_level)

    return True


def get_current_log_level() -> str:
    """현재 로그 레벨 반환

    Returns:
        현재 로그 레벨 문자열
    """
    level = logging.getLogger().level
    return logging.getLevelName(level)


def log_metrics(
    logger: logging.Logger,
    *,
    latency_ms: float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cache_hits: int | None = None,
    cache_misses: int | None = None,
    api_retries: int | None = None,
    api_failures: int | None = None,
) -> None:
    """표준화된 메트릭 로깅: latency, 토큰 처리율, 캐시 히트율을 계산해 기록.
    """
    metrics: dict[str, float | int] = {}
    if prompt_tokens is not None:
        metrics["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        metrics["completion_tokens"] = completion_tokens

    if latency_ms is not None:
        metrics["latency_ms"] = round(latency_ms, 2)

    total_tokens = 0
    for t in (prompt_tokens, completion_tokens):
        if t:
            total_tokens += t
    if total_tokens:
        metrics["total_tokens"] = total_tokens
    if latency_ms and latency_ms > 0 and total_tokens:
        metrics["tokens_per_sec"] = round(total_tokens / (latency_ms / 1000), 3)

    if cache_hits is not None or cache_misses is not None:
        hits = cache_hits or 0
        misses = cache_misses or 0
        total = hits + misses
        metrics["cache_hit_ratio"] = round(hits / total, 3) if total else 0.0
        metrics["cache_hits"] = hits
        metrics["cache_misses"] = misses

    if api_retries is not None:
        metrics["api_retries"] = api_retries
    if api_failures is not None:
        metrics["api_failures"] = api_failures

    logger.info("metrics", extra={"metrics": metrics})


class StructuredLogger:
    """구조화된 로깅을 위한 래퍼 클래스

    API 호출, 캐시 이벤트 등을 표준화된 형식으로 로깅합니다.
    """

    def __init__(self, name: str):
        """StructuredLogger 초기화

        Args:
            name: 로거 이름
        """
        self.logger = logging.getLogger(name)

    def log_api_call(
        self,
        model: str,
        prompt_tokens: int,
        response_tokens: int,
        latency_ms: float,
        status: str,
    ) -> None:
        """API 호출 로그 (분석 용이)

        Args:
            model: 모델 이름
            prompt_tokens: 프롬프트 토큰 수
            response_tokens: 응답 토큰 수
            latency_ms: 응답 시간 (밀리초)
            status: 상태 (success, error 등)
        """
        self.logger.info(
            "api_call",
            extra={
                "event_type": "api_call",
                "model": model,
                "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens,
                "latency_ms": latency_ms,
                "status": status,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_cache_event(
        self,
        cache_key: str,
        hit: bool,
        ttl_remaining: int | None = None,
    ) -> None:
        """캐시 이벤트 로그

        Args:
            cache_key: 캐시 키
            hit: 캐시 히트 여부
            ttl_remaining: 남은 TTL (초)
        """
        self.logger.debug(
            "cache_event",
            extra={
                "event_type": "cache",
                "cache_key": cache_key,
                "hit": hit,
                "ttl_remaining": ttl_remaining,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_error(
        self,
        error_type: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """에러 로그

        Args:
            error_type: 에러 유형
            message: 에러 메시지
            context: 추가 컨텍스트 정보
        """
        extra: dict[str, Any] = {
            "event_type": "error",
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
        }
        if context:
            extra["context"] = context

        self.logger.error(message, extra=extra)

    def log_workflow(
        self,
        workflow_name: str,
        stage: str,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """워크플로우 진행 로그

        Args:
            workflow_name: 워크플로우 이름
            stage: 단계 (started, completed, failed 등)
            duration_ms: 소요 시간 (밀리초)
            metadata: 추가 메타데이터
        """
        extra: dict[str, Any] = {
            "event_type": "workflow",
            "workflow_name": workflow_name,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        }
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms
        if metadata:
            extra["metadata"] = metadata

        self.logger.info(f"workflow:{workflow_name}:{stage}", extra=extra)


__all__ = [
    "setup_logging",
    "log_metrics",
    "SensitiveDataFilter",
    "_resolve_log_level",
    "_build_file_handler",
    "_build_console_handler",
    "get_log_level",
    "set_log_level",
    "get_current_log_level",
    "StructuredLogger",
]
