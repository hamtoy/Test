import pytest

from src.config import AppConfig


def test_max_concurrency_out_of_range():
    with pytest.raises(ValueError):
        AppConfig(max_concurrency=0)


def test_temperature_out_of_range():
    with pytest.raises(ValueError):
        AppConfig(temperature=2.5)
