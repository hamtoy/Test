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
    logger, listener = setup_logging(env="local")
    try:
        handlers = listener.handlers
        assert any(isinstance(h, RichHandler) for h in handlers)

        file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers
        for handler in file_handlers:
            # local uses plain text formatter, not JSON
            assert not isinstance(handler.formatter, JsonFormatter)
    finally:
        _cleanup(listener)


def test_production_logging_uses_json_file_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    logger, listener = setup_logging(env="production")
    try:
        handlers = listener.handlers
        assert not any(isinstance(h, RichHandler) for h in handlers)

        file_handlers = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers
        assert any(isinstance(h.formatter, JsonFormatter) for h in file_handlers)
    finally:
        _cleanup(listener)
