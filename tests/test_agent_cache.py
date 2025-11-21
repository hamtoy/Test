import hashlib
import json
from datetime import datetime, timedelta, timezone
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

    monkeypatch.setattr(
        "google.generativeai.caching.CachedContent.get",
        lambda *args, **kwargs: DummyCache(),
    )
    monkeypatch.setattr(
        "google.generativeai.caching.CachedContent.create",
        lambda **kwargs: pytest.fail(
            "create should not be called when cache is reused"
        ),
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


def test_local_cache_ttl_expiration(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LOCAL_CACHE_DIR", str(tmp_path / ".cache"))

    jinja_env = MagicMock()
    jinja_env.get_template.return_value.render.return_value = "prompt"
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)

    fingerprint = "abc"
    manifest_path = agent._local_cache_manifest_path()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    expired_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    manifest = {
        fingerprint: {
            "name": "cached",
            "created": expired_time.isoformat(),
            "ttl_minutes": 10,
        }
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert agent._load_local_cache(fingerprint, ttl_minutes=10) is None


def test_local_cache_ttl_returns_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LOCAL_CACHE_DIR", str(tmp_path / ".cache"))

    jinja_env = MagicMock()
    jinja_env.get_template.return_value.render.return_value = "prompt"
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)

    fingerprint = "abc"
    manifest_path = agent._local_cache_manifest_path()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    manifest = {
        fingerprint: {
            "name": "cached-keep",
            "created": now.isoformat(),
            "ttl_minutes": 10,
        }
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class DummyCache:
        name = "cached-keep"

    monkeypatch.setattr(
        "google.generativeai.caching.CachedContent.get",
        lambda *args, **kwargs: DummyCache(),
    )

    cache = agent._load_local_cache(fingerprint, ttl_minutes=10)
    assert cache.name == "cached-keep"
