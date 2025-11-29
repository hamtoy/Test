from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import AppConfig

VALID_API_KEY = "AIza" + "A" * 35


def test_api_key_validation_valid() -> None:
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)
    assert config.api_key == VALID_API_KEY


def test_api_key_validation_default_placeholder() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="your_api_key_here")
    assert "GEMINI_API_KEY is not set" in str(excinfo.value)


def test_api_key_validation_invalid_format() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 34 + "*")
    assert "Invalid format" in str(excinfo.value)


def test_api_key_validation_invalid_prefix() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="WRONG" + "A" * 35)
    assert "Must start with 'AIza'" in str(excinfo.value)


def test_api_key_validation_invalid_length() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 10)
    assert "exactly 39 characters" in str(excinfo.value)


def test_log_level_validation() -> None:
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="debug")
    assert config.log_level == "DEBUG"

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="INVALID")


def test_directories_are_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    expected_dirs = [
        Path(tmp_path) / "data" / "inputs",
        Path(tmp_path) / "data" / "outputs",
        Path(tmp_path) / "templates",
    ]

    for dir_path in expected_dirs:
        assert dir_path.is_dir()


def test_cache_stats_path_and_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("CACHE_STATS_FILE", "stats/cache.jsonl")
    monkeypatch.setenv("CACHE_STATS_MAX_ENTRIES", "50")
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    assert config.cache_stats_path == Path(tmp_path) / "stats" / "cache.jsonl"
    assert config.cache_stats_max_entries == 50

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, CACHE_STATS_MAX_ENTRIES=0)


def test_rag_dependencies_validation_missing_uri() -> None:
    """Test that RAG validation fails when URI is missing but enable_rag is True."""
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(
            GEMINI_API_KEY=VALID_API_KEY,
            ENABLE_RAG=True,
        )
    assert "ENABLE_RAG=True 설정 시 필수" in str(excinfo.value)
    assert "neo4j_uri" in str(excinfo.value)


def test_rag_dependencies_validation_missing_password() -> None:
    """Test that RAG validation fails when password is missing."""
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(
            GEMINI_API_KEY=VALID_API_KEY,
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
        )
    assert "NEO4J_URI 설정 시 필수" in str(excinfo.value)
    assert "neo4j_password" in str(excinfo.value)


def test_rag_dependencies_validation_valid() -> None:
    """Test that RAG validation passes when all fields are set."""
    config = AppConfig(
        GEMINI_API_KEY=VALID_API_KEY,
        ENABLE_RAG=True,
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
    )
    assert config.enable_rag is True
    assert config.neo4j_uri == "bolt://localhost:7687"


def test_rag_disabled_no_validation() -> None:
    """Test that RAG validation is skipped when ENABLE_RAG is False and no Neo4j URI."""
    config = AppConfig(
        GEMINI_API_KEY=VALID_API_KEY,
        ENABLE_RAG=False,
    )
    assert config.enable_rag is False
    assert config.neo4j_uri is None
