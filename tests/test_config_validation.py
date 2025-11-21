import pytest
from pydantic import ValidationError
from src.config import AppConfig

def test_api_key_validation_valid():
    # Valid key format
    config = AppConfig(GEMINI_API_KEY="AIza123456789012345678901234567890")
    assert config.api_key == "AIza123456789012345678901234567890"

def test_api_key_validation_default_placeholder():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="your_api_key_here")
    assert "GEMINI_API_KEY is not set" in str(excinfo.value)

def test_api_key_validation_invalid_format():
    with pytest.raises(ValidationError) as excinfo:
        AppConfig(GEMINI_API_KEY="InvalidKeyFormat")
    assert "Invalid GEMINI_API_KEY format" in str(excinfo.value)

def test_log_level_validation():
    config = AppConfig(GEMINI_API_KEY="AIza123456789012345678901234567890", LOG_LEVEL="debug")
    assert config.log_level == "DEBUG"

    with pytest.raises(ValidationError):
        AppConfig(GEMINI_API_KEY="AIza123456789012345678901234567890", LOG_LEVEL="INVALID")
