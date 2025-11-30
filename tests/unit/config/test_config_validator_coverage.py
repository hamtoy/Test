"""Tests for src/config/validator.py to improve coverage."""

import pytest

from src.config.validator import EnvValidator, ValidationError, validate_environment


class TestEnvValidator:
    """Tests for EnvValidator class."""

    def test_validate_gemini_api_key_valid(self) -> None:
        """Test valid Gemini API key."""
        validator = EnvValidator()
        # Valid key: starts with AIza and is 39 characters
        valid_key = "AIza" + "A" * 35
        validator.validate_gemini_api_key(valid_key)

    def test_validate_gemini_api_key_invalid_prefix(self) -> None:
        """Test API key with invalid prefix."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_gemini_api_key("WRONG" + "A" * 34)
        assert (
            "Must start with 'AIza'" in str(exc.value)
            or "must start with" in str(exc.value).lower()
        )

    def test_validate_gemini_api_key_invalid_length(self) -> None:
        """Test API key with invalid length."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_gemini_api_key("AIza" + "A" * 10)
        assert "39 characters" in str(exc.value)

    def test_validate_port_valid(self) -> None:
        """Test valid port number."""
        validator = EnvValidator()
        validator.validate_port("8080")
        validator.validate_port("1024")
        validator.validate_port("65535")

    def test_validate_port_invalid_range_low(self) -> None:
        """Test port number below valid range."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_port("80")
        assert "between 1024-65535" in str(exc.value)

    def test_validate_port_invalid_range_high(self) -> None:
        """Test port number above valid range."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_port("70000")
        assert "between 1024-65535" in str(exc.value)

    def test_validate_port_not_integer(self) -> None:
        """Test port that is not an integer."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_port("not_a_port")
        assert "must be an integer" in str(exc.value)

    def test_validate_url_valid_http(self) -> None:
        """Test valid HTTP URL."""
        validator = EnvValidator()
        validator.validate_url("http://localhost:8080")
        validator.validate_url("https://example.com")
        validator.validate_url("http://192.168.1.1:8080")

    def test_validate_url_valid_bolt(self) -> None:
        """Test valid bolt URL (Neo4j)."""
        validator = EnvValidator()
        validator.validate_url("bolt://localhost:7687")

    def test_validate_url_invalid(self) -> None:
        """Test invalid URL format."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_url("not_a_url")
        assert "Invalid URL format" in str(exc.value)

    def test_validate_log_level_valid(self) -> None:
        """Test valid log levels."""
        validator = EnvValidator()
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            validator.validate_log_level(level)

    def test_validate_log_level_case_insensitive(self) -> None:
        """Test log level validation is case insensitive."""
        validator = EnvValidator()
        validator.validate_log_level("debug")
        validator.validate_log_level("Info")

    def test_validate_log_level_invalid(self) -> None:
        """Test invalid log level."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_log_level("INVALID")
        assert "Invalid log level" in str(exc.value)

    def test_validate_positive_int_valid(self) -> None:
        """Test valid positive integer."""
        validator = EnvValidator()
        validator.validate_positive_int("1", "TEST_VAR")
        validator.validate_positive_int("100", "TEST_VAR")
        validator.validate_positive_int("999999", "TEST_VAR")

    def test_validate_positive_int_zero(self) -> None:
        """Test zero (not positive)."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_positive_int("0", "TEST_VAR")
        assert "positive integer" in str(exc.value)

    def test_validate_positive_int_negative(self) -> None:
        """Test negative number."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_positive_int("-1", "TEST_VAR")
        assert "positive integer" in str(exc.value)

    def test_validate_positive_int_not_integer(self) -> None:
        """Test non-integer value."""
        validator = EnvValidator()
        with pytest.raises(ValidationError) as exc:
            validator.validate_positive_int("abc", "TEST_VAR")
        assert "must be an integer" in str(exc.value)


class TestValidateAll:
    """Tests for validate_all method."""

    def test_validate_all_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation when GEMINI_API_KEY is missing."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("GEMINI_API_KEY" in e[0] for e in errors)

    def test_validate_all_valid_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation with valid API key."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        validator = EnvValidator()
        errors = validator.validate_all()
        # Should not have API key errors
        assert not any("GEMINI_API_KEY" in e[0] for e in errors)

    def test_validate_all_invalid_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "invalid_key")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("GEMINI_API_KEY" in e[0] for e in errors)

    def test_validate_all_invalid_neo4j_uri(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid NEO4J_URI."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("NEO4J_URI", "invalid_uri")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("NEO4J_URI" in e[0] for e in errors)

    def test_validate_all_valid_neo4j_uri(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid NEO4J_URI."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("NEO4J_URI" in e[0] for e in errors)

    def test_validate_all_invalid_redis_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid REDIS_URL."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("REDIS_URL", "invalid_redis")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("REDIS_URL" in e[0] for e in errors)

    def test_validate_all_valid_redis_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid REDIS_URL."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("REDIS_URL" in e[0] for e in errors)

    def test_validate_all_valid_redis_ssl_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid REDIS_URL using SSL."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("REDIS_URL", "rediss://localhost:6379")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("REDIS_URL" in e[0] for e in errors)

    def test_validate_all_invalid_log_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid LOG_LEVEL."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("LOG_LEVEL" in e[0] for e in errors)

    def test_validate_all_valid_log_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid LOG_LEVEL."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("LOG_LEVEL" in e[0] for e in errors)

    def test_validate_all_invalid_max_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid GEMINI_MAX_OUTPUT_TOKENS."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_MAX_OUTPUT_TOKENS", "0")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("GEMINI_MAX_OUTPUT_TOKENS" in e[0] for e in errors)

    def test_validate_all_valid_max_tokens(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid GEMINI_MAX_OUTPUT_TOKENS."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_MAX_OUTPUT_TOKENS", "1000")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("GEMINI_MAX_OUTPUT_TOKENS" in e[0] for e in errors)

    def test_validate_all_invalid_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid GEMINI_TIMEOUT."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_TIMEOUT", "-1")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("GEMINI_TIMEOUT" in e[0] for e in errors)

    def test_validate_all_valid_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation with valid GEMINI_TIMEOUT."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_TIMEOUT", "30")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("GEMINI_TIMEOUT" in e[0] for e in errors)

    def test_validate_all_invalid_concurrency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with invalid GEMINI_MAX_CONCURRENCY."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_MAX_CONCURRENCY", "abc")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert any("GEMINI_MAX_CONCURRENCY" in e[0] for e in errors)

    def test_validate_all_valid_concurrency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test validation with valid GEMINI_MAX_CONCURRENCY."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("GEMINI_MAX_CONCURRENCY", "5")
        validator = EnvValidator()
        errors = validator.validate_all()
        assert not any("GEMINI_MAX_CONCURRENCY" in e[0] for e in errors)


class TestValidateEnvironment:
    """Tests for validate_environment function."""

    def test_validate_environment_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test successful environment validation."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        result = validate_environment()
        assert result is True
        captured = capsys.readouterr()
        assert "validated" in captured.out.lower() or "✅" in captured.out

    def test_validate_environment_failure(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test failed environment validation."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = validate_environment()
        assert result is False
        captured = capsys.readouterr()
        assert "failed" in captured.out.lower() or "❌" in captured.out

    def test_validate_environment_strict_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test strict mode raises SystemExit on failure."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            validate_environment(strict=True)
        assert exc.value.code == 1

    def test_validate_environment_strict_mode_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test strict mode does not raise on success."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        result = validate_environment(strict=True)
        assert result is True
