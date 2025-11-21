import logging
import logging.handlers
import os
import queue
import re
from typing import Any, Tuple

from pythonjsonlogger.json import JsonFormatter
from rich.logging import RichHandler

from src.constants import SENSITIVE_PATTERN


def _resolve_log_level() -> int:
    """Resolve log level from LOG_LEVEL env var, defaulting to INFO."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
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
                        new_args.append(self.sensitive_regex.sub("[FILTERED_API_KEY]", arg))
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)

        return True

def _build_file_handler(log_level: int, use_json: bool, sensitive_filter: logging.Filter) -> logging.Handler:
    """Create RotatingFileHandler with optional JSON formatting."""
    log_file = os.getenv("LOG_FILE", "app.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    if use_json:
        formatter = JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)
    return file_handler


def _build_console_handler(log_level: int, sensitive_filter: logging.Filter) -> logging.Handler:
    """Create Rich console handler."""
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
    )
    console_handler.setLevel(log_level)
    console_handler.addFilter(sensitive_filter)
    return console_handler


def setup_logging(env: str | None = None) -> Tuple[logging.Logger, logging.handlers.QueueListener]:
    """
    [Non-Blocking Logging] QueueHandler 패턴 + 환경별 포맷/출력 제어

    - production: JSON 포맷, 파일만(회전)
    - local/dev: 텍스트 포맷, 콘솔 + 파일(회전)
    """
    log_env = (env or os.getenv("APP_ENV") or "local").lower()
    is_production = log_env in {"prod", "production"}

    log_queue: queue.Queue[Any] = queue.Queue(-1)  # 무제한 큐
    log_level = _resolve_log_level()
    sensitive_filter = SensitiveDataFilter()

    handlers = []

    file_handler = _build_file_handler(
        log_level=log_level,
        use_json=is_production,
        sensitive_filter=sensitive_filter,
    )
    handlers.append(file_handler)

    if not is_production:
        handlers.append(_build_console_handler(log_level, sensitive_filter))

    listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True,
    )

    queue_handler = logging.handlers.QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 기존 핸들러 제거 (중복 방지)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(queue_handler)
    listener.start()

    return logging.getLogger("GeminiWorkflow"), listener
