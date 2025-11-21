import hashlib
from unittest.mock import MagicMock

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "A" * 35


@pytest.mark.asyncio
async def test_create_context_cache_reuses_local(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LOCAL_CACHE_DIR", str(tmp_path / ".cache"))

    # Patch caching to avoid network calls
    class DummyCache:
        name = "cached-content"

    monkeypatch.setattr("google.generativeai.caching.CachedContent.get", lambda *args, **kwargs: DummyCache())
    monkeypatch.setattr(
        "google.generativeai.caching.CachedContent.create",
        lambda **kwargs: pytest.fail("create should not be called when cache is reused"),
    )

    jinja_env = MagicMock()
    jinja_env.get_template.return_value.render.return_value = "prompt"
    config = AppConfig()
    agent = GeminiAgent(config, jinja_env=jinja_env)

    combined_content = "prompt" + "\n\n" + "ocr text"
    fingerprint = hashlib.sha256(combined_content.encode("utf-8")).hexdigest()
    agent._store_local_cache(fingerprint, "cached-content", config.cache_ttl_minutes)

    cache = await agent.create_context_cache("ocr text")
    assert cache.name == "cached-content"
