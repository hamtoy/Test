import os
import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure AppConfig validation passes with valid mock values."""
    # AIza + 35 characters = 39 characters total
    mock_key = "AIza" + "0" * 35
    monkeypatch.setenv("GEMINI_API_KEY", mock_key)
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")

