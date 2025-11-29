from __future__ import annotations

import types
from typing import Any

import pytest

from src.caching import layer as caching_layer


def test_caching_layer_prefers_cache_and_invalidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return False

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            self.calls += 1
            return [{"id": "r1", "text": "T", "section": "S"}]

    class _FakeGraph:
        def __init__(self) -> None:
            self.session_obj = _FakeSession()

        def session(self) -> Any:
            return self.session_obj

    kg = types.SimpleNamespace(_graph=_FakeGraph())

    class _FakeRedis:
        def __init__(self) -> None:
            self.store = {}

        def get(self, key: Any) -> Any:
            return self.store.get(key)

        def setex(self, key: Any, ttl: Any, value: Any) -> None:
            self.store[key] = value

        def keys(self, pattern: Any) -> Any:
            return list(self.store.keys())

        def delete(self, *keys: Any) -> Any:
            removed = 0
            for k in keys:
                if k in self.store:
                    removed += 1
                    self.store.pop(k, None)
            return removed

    monkeypatch.setattr(caching_layer, "redis", object())
    fake_redis = _FakeRedis()
    layer = caching_layer.CachingLayer(kg, redis_client=fake_redis)  # type: ignore[arg-type]

    first = layer.get_rules_cached("summary")
    second = layer.get_rules_cached("summary")
    assert first == second == [{"id": "r1", "text": "T", "section": "S"}]
    assert kg._graph.session_obj.calls == 1  # cache hit skips graph
    assert layer.invalidate_cache() == 1
