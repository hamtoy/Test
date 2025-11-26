import logging
import logging.handlers
import os
import queue
import re
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
    """
    [Security] 로그에서 민감한 정보(API Key 등)를 마스킹하는 필터
    """

    sensitive_regex = re.compile(SENSITIVE_PATTERN)

    def filter(self, record):
        msg = record.getMessage()
        if "AIza" in msg:
            record.msg = self.sensitive_regex.sub("[FILTERED_API_KEY]", msg)

            if record.args:
                new_args = []
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
    """
    [Non-Blocking Logging] QueueHandler 패턴 + 환경별 포맷/출력 제어

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
    """
    표준화된 메트릭 로깅: latency, 토큰 처리율, 캐시 히트율을 계산해 기록.
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
