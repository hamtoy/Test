"""Tests for src.web.rate_limit utilities."""

from __future__ import annotations

import types
from typing import Any, cast

import pytest
from fastapi import Request

import src.web.rate_limit as rl


class _FakeLimiter:
    def __init__(self) -> None:
        self.enter_count = 0
        self.acquire_count = 0

    async def __aenter__(self) -> "_FakeLimiter":
        self.enter_count += 1
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        tb: Any,
    ) -> None:
        return None

    async def acquire(self) -> None:
        self.acquire_count += 1


def test_get_limiter_caches_instance() -> None:
    rl._limiters.clear()
    limiter1 = rl.get_limiter("test", rate=1.0, burst=1)
    limiter2 = rl.get_limiter("test", rate=5.0, burst=5)
    assert limiter1 is limiter2


@pytest.mark.asyncio
async def test_rate_limit_decorator_uses_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeLimiter()
    monkeypatch.setattr(rl, "get_limiter", lambda *_a, **_k: fake)

    @rl.rate_limit("qa_generate")
    async def _handler(x: int) -> int:
        return x + 1

    assert await _handler(1) == 2
    assert fake.enter_count == 1


@pytest.mark.asyncio
async def test_check_rate_limit_acquires(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeLimiter()
    monkeypatch.setattr(rl, "get_limiter", lambda *_a, **_k: fake)
    await rl.check_rate_limit(cast(Request, types.SimpleNamespace()), name="default")
    assert fake.acquire_count == 1
