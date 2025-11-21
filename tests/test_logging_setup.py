import logging
from logging.handlers import RotatingFileHandler

from pythonjsonlogger.json import JsonFormatter
from rich.logging import RichHandler

from src.logging_setup import setup_logging


def _cleanup(listener: logging.handlers.QueueListener) -> None:
    listener.stop()
    root = logging.getLogger()
    root.handlers.clear()


def test_local_logging_uses_console_and_text_formatter(tmp_path, monkeypatch):
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


def test_production_logging_uses_json_file_only(tmp_path, monkeypatch):
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
