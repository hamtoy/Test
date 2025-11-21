import pytest

from src.config import AppConfig


def test_max_concurrency_out_of_range():
    with pytest.raises(ValueError):
        AppConfig(max_concurrency=0)


def test_temperature_out_of_range():
    with pytest.raises(ValueError):
        AppConfig(temperature=2.5)


def test_api_key_format_invalid():
    with pytest.raises(ValueError):
        AppConfig(GEMINI_API_KEY="bad-key-format")
