"""Integration-style test for streaming QA endpoint."""

from typing import Any, AsyncIterator

import pytest
from fastapi.testclient import TestClient

from src.web import api


class _FakeAgent:
    async def generate_stream(self, prompt: str, **_: Any) -> AsyncIterator[str]:
        assert prompt == "hello"
        yield "hi "
        yield "there"


@pytest.mark.integration
def test_streaming_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SSE endpoint streams chunks from agent."""

    async def _noop_init() -> None:
        return None

    monkeypatch.setattr(api, "init_resources", _noop_init)
    monkeypatch.setattr(api, "agent", _FakeAgent())

    with TestClient(api.app) as client:
        resp = client.post("/api/qa/generate/stream", json={"prompt": "hello"})
        assert resp.status_code == 200
        body = resp.text
        assert "data:" in body
        assert "hi " in body
        assert "there" in body
