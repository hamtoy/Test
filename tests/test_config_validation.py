from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import AppConfig

VALID_API_KEY = "AIza" + "A" * 35


def test_api_key_validation_valid():
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)
    assert config.api_key == VALID_API_KEY


def test_api_key_validation_default_placeholder():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="your_api_key_here")
    assert "GEMINI_API_KEY is not set" in str(excinfo.value)


def test_api_key_validation_invalid_format():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 34 + "*")
    assert "Invalid format" in str(excinfo.value)


def test_api_key_validation_invalid_prefix():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="WRONG" + "A" * 35)
    assert "Must start with 'AIza'" in str(excinfo.value)


def test_api_key_validation_invalid_length():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 10)
    assert "exactly 39 characters" in str(excinfo.value)


def test_log_level_validation():
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="debug")
    assert config.log_level == "DEBUG"

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="INVALID")


def test_directories_are_created(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    expected_dirs = [
        Path(tmp_path) / "data" / "inputs",
        Path(tmp_path) / "data" / "outputs",
        Path(tmp_path) / "templates",
    ]

    for dir_path in expected_dirs:
        assert dir_path.is_dir()


def test_cache_stats_path_and_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("CACHE_STATS_FILE", "stats/cache.jsonl")
    monkeypatch.setenv("CACHE_STATS_MAX_ENTRIES", "50")
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    assert config.cache_stats_path == Path(tmp_path) / "stats" / "cache.jsonl"
    assert config.cache_stats_max_entries == 50

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, CACHE_STATS_MAX_ENTRIES=0)
