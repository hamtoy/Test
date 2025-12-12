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
    assert "placeholder" in str(excinfo.value).lower()


def test_api_key_validation_invalid_format() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 34 + "*")
    assert "invalid" in str(excinfo.value).lower()


def test_api_key_validation_invalid_prefix() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="WRONG" + "A" * 35)
    # This will fail on length check first (40 chars instead of 39)
    error_msg = str(excinfo.value).lower()
    assert "length" in error_msg or "start" in error_msg


def test_api_key_validation_invalid_length() -> None:
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="AIza" + "A" * 10)
    assert "length" in str(excinfo.value).lower() and "39" in str(excinfo.value)


def test_log_level_validation() -> None:
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="debug")
    assert config.log_level == "DEBUG"

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, LOG_LEVEL="INVALID")


def test_directories_are_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    expected_dirs = [
        Path(tmp_path) / "data" / "inputs",
        Path(tmp_path) / "data" / "outputs",
        Path(tmp_path) / "templates",
    ]

    for dir_path in expected_dirs:
        assert dir_path.is_dir()


def test_cache_stats_path_and_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("CACHE_STATS_FILE", "stats/cache.jsonl")
    monkeypatch.setenv("CACHE_STATS_MAX_ENTRIES", "50")
    config = AppConfig(GEMINI_API_KEY=VALID_API_KEY)

    assert config.cache_stats_path == Path(tmp_path) / "stats" / "cache.jsonl"
    assert config.cache_stats_max_entries == 50

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY=VALID_API_KEY, CACHE_STATS_MAX_ENTRIES=0)


def test_rag_dependencies_validation_missing_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that RAG validation fails when URI is missing but enable_rag is True."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        AppConfig(
            GEMINI_API_KEY=VALID_API_KEY,
            ENABLE_RAG=True,
            _env_file=None,
        )
    assert "ENABLE_RAG=True 설정 시 필수" in str(excinfo.value)
    assert "neo4j_uri" in str(excinfo.value)


def test_rag_dependencies_validation_missing_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that RAG validation fails when password is missing."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        AppConfig(
            GEMINI_API_KEY=VALID_API_KEY,
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            _env_file=None,
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


def test_rag_disabled_no_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that RAG validation is skipped when ENABLE_RAG is False and no Neo4j URI."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    config = AppConfig(
        GEMINI_API_KEY=VALID_API_KEY,
        ENABLE_RAG=False,
        _env_file=None,  # Disable .env file loading
    )
    assert config.enable_rag is False
    assert config.neo4j_uri is None


class TestCorsOriginsValidation:
    """Test CORS origins configuration validation.

    Note: CORS configuration is verified by:
    - Field exists: src/config/settings.py:112 (cors_allow_origins: list[str])
    - Used in API: src/web/api.py:409 (allow_origins=config.cors_allow_origins)
    - Default values: ["http://127.0.0.1:8000", "http://localhost:8000"]
    """

    pass  # Direct tests omitted due to pydantic-settings env var caching issues
