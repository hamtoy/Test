import logging
from src.logging_setup import SensitiveDataFilter

class TestSecurity:
    """보안 관련 기능 테스트"""

    def test_sensitive_data_filter_masks_api_key(self):
        """SensitiveDataFilter가 API Key를 마스킹하는지 확인"""
        filter = SensitiveDataFilter()
        
        # 가짜 API Key 생성 (AIza로 시작하는 39자)
        fake_key = "AIzaSyD-1234567890abcdefghijklmnopqrstu"
        assert len(fake_key) == 39
        
        # 1. 메시지에 키가 포함된 경우
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg=f"Using API Key: {fake_key}", args=(), exc_info=None
        )
        
        filter.filter(record)
        
        assert "[FILTERED_API_KEY]" in record.msg
        assert fake_key not in record.msg
        
    def test_sensitive_data_filter_masks_api_key_in_args(self):
        """SensitiveDataFilter가 args에 포함된 API Key도 마스킹하는지 확인"""
        filter = SensitiveDataFilter()
        fake_key = "AIzaSyD-1234567890abcdefghijklmnopqrstu"
        
        # 2. args에 키가 포함된 경우
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg="API Key: %s", args=(fake_key,), exc_info=None
        )
        
        filter.filter(record)
        
        # args가 튜플이므로 수정되었는지 확인
        assert "[FILTERED_API_KEY]" in record.args[0]
        assert fake_key not in record.args[0]

    def test_sensitive_data_filter_ignores_safe_logs(self):
        """민감 정보가 없는 로그는 건드리지 않는지 확인"""
        filter = SensitiveDataFilter()
        safe_msg = "This is a safe log message."
        
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1,
            msg=safe_msg, args=(), exc_info=None
        )
        
        filter.filter(record)
        
        assert record.msg == safe_msg
