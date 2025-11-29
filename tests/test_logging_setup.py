import pytest
import logging
from logging.handlers import RotatingFileHandler

from pythonjsonlogger.json import JsonFormatter
from rich.logging import RichHandler

from src.infra.logging import (
    SensitiveDataFilter,
    _build_file_handler,
    _resolve_log_level,
    setup_logging,
)
from pathlib import Path


def _cleanup(listener: logging.handlers.QueueListener) -> None:
    listener.stop()
    root = logging.getLogger()
    root.handlers.clear()


def test_local_logging_uses_console_and_text_formatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    logger, listener = setup_logging(env="local", log_level="DEBUG")
    try:
        handlers = listener.handlers
        assert any(isinstance(h, RichHandler) for h in handlers)

        file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 2  # info + error
        for handler in file_handlers:
            # local uses plain text formatter, not JSON
            assert not isinstance(handler.formatter, JsonFormatter)
    finally:
        _cleanup(listener)


def test_production_logging_uses_json_file_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    logger, listener = setup_logging(env="production", log_level="INFO")
    try:
        handlers = listener.handlers
        assert not any(isinstance(h, RichHandler) for h in handlers)

        file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 2
        assert all(isinstance(h.formatter, JsonFormatter) for h in file_handlers)
    finally:
        _cleanup(listener)


def test_sensitive_data_filter_masks_api_key() -> None:
    filt = SensitiveDataFilter()
    raw_key = "AIza" + "0" * 35
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"Key: {raw_key}",
        args=(),
        exc_info=None,
        func=None,
        sinfo=None,
    )

    assert filt.filter(record)
    assert "[FILTERED_API_KEY]" in record.msg
    assert "AIza" not in record.msg


def test_build_file_handler_formats(tmp_path: Path) -> None:
    filt = logging.Filter()
    json_handler = _build_file_handler(
        logging.INFO, True, filt, str(tmp_path / "log.json")
    )
    text_handler = _build_file_handler(
        logging.INFO, False, filt, str(tmp_path / "log.txt")
    )

    assert isinstance(json_handler.formatter, JsonFormatter)
    assert not isinstance(text_handler.formatter, JsonFormatter)


def test_resolve_log_level_invalid() -> None:
    assert _resolve_log_level("NOT_A_LEVEL") == logging.INFO
