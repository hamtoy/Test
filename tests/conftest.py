import os
import pytest


@pytest.fixture(autouse=True)
def _set_dummy_api_key(monkeypatch):
    """Ensure AppConfig validation passes without a real API key."""
    monkeypatch.setenv("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "dummy-test-key"))
