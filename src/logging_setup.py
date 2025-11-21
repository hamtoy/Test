import logging
import logging.handlers
import os
import queue
from typing import Tuple
from rich.logging import RichHandler


def _resolve_log_level() -> int:
    """Resolve log level from LOG_LEVEL env var, defaulting to INFO."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level_value = getattr(logging, level_name, logging.INFO)
    return level_value if isinstance(level_value, int) else logging.INFO


def setup_logging() -> Tuple[logging.Logger, logging.handlers.QueueListener]:
    """
    [Non-Blocking Logging] QueueHandler 패턴 적용
    
    1. 메인 프로세스: QueueHandler를 통해 메모리 큐에 로그를 밀어넣음 (Non-blocking)
    2. 별도 스레드: QueueListener가 큐에서 로그를 꺼내 실제 파일/콘솔에 기록 (Blocking I/O 분리)
    
    Returns:
        logger: 애플리케이션 로거
        listener: 로그 리스너 (앱 종료 시 stop() 호출 필수)
    """
    log_queue = queue.Queue(-1)  # 무제한 큐
    
    log_level = _resolve_log_level()

    # 1. 실제 처리를 담당할 핸들러들 (Blocking I/O 발생)
    # 콘솔 핸들러: Rich
    console_handler = RichHandler(
        rich_tracebacks=True, 
        show_time=False,
        show_path=False
    )
    console_handler.setLevel(log_level)
    
    # 파일 핸들러: Plain Text
    file_handler = logging.FileHandler("app.log", encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] %(levelname)s | %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    
    # 2. QueueListener 생성 (별도 스레드에서 핸들러 실행)
    listener = logging.handlers.QueueListener(
        log_queue, 
        console_handler, 
        file_handler,
        respect_handler_level=True
    )
    
    # 3. 메인 로거는 QueueHandler만 가짐
    queue_handler = logging.handlers.QueueHandler(log_queue)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 기존 핸들러 제거 (중복 방지)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(queue_handler)
    
    # 리스너 시작 (백그라운드 스레드)
    listener.start()
    
    return logging.getLogger("GeminiWorkflow"), listener
