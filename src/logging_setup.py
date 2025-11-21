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


class SensitiveDataFilter(logging.Filter):
    """
    [Security] 로그에서 민감한 정보(API Key 등)를 마스킹하는 필터
    """
    def filter(self, record):
        msg = record.getMessage()
        # API Key 패턴 (AIza로 시작하는 39자 문자열)
        # 정규식 대신 간단한 문자열 치환으로 성능 확보 (로그는 빈번하게 발생하므로)
        if "AIza" in msg:
            # 단순 치환: AIza... -> [FILTERED_API_KEY]
            # 실제로는 정규식을 쓰는 게 더 안전하지만, 여기서는 간단히 처리
            import re
            # AIza로 시작하고 뒤에 35개의 문자가 오는 패턴 (총 39자)
            pattern = r"AIza[0-9A-Za-z-_]{35}"
            record.msg = re.sub(pattern, "[FILTERED_API_KEY]", msg)
            # args가 있는 경우 포맷팅이 다시 일어날 수 있으므로 주의 필요
            # 여기서는 msg 자체를 수정했으므로 args를 비워주는 것이 안전할 수 있음
            # 하지만 record.msg는 포맷팅 전의 문자열일 수 있음.
            # logging 시스템은 record.msg % record.args 를 수행함.
            # 따라서 record.args에도 민감 정보가 있을 수 있음.
            # 가장 안전한 방법은 포맷팅이 완료된 메시지를 수정하는 것인데, 
            # Filter에서는 record.getMessage()로 확인만 하고 수정은 record.msg/args를 건드려야 함.
            # 간단하게 구현하기 위해, 이미 포맷팅된 메시지를 record.msg에 넣고 args를 비우는 방식을 사용하거나
            # Formatter에서 처리하는 것이 더 깔끔할 수 있음.
            # 여기서는 Filter에서 record.msg를 수정하는 방식을 시도.
            
            # 더 강력한 방법: record.args도 검사
            if record.args:
                new_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        new_args.append(re.sub(pattern, "[FILTERED_API_KEY]", arg))
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)
                
        return True

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

    # [Security] 민감 정보 필터 생성
    sensitive_filter = SensitiveDataFilter()

    # 1. 실제 처리를 담당할 핸들러들 (Blocking I/O 발생)
    # 콘솔 핸들러: Rich
    console_handler = RichHandler(
        rich_tracebacks=True, 
        show_time=False,
        show_path=False
    )
    console_handler.setLevel(log_level)
    console_handler.addFilter(sensitive_filter)  # 필터 적용
    
    # 파일 핸들러: Plain Text
    file_handler = logging.FileHandler("app.log", encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] %(levelname)s | %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    file_handler.addFilter(sensitive_filter)  # 필터 적용
    
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
