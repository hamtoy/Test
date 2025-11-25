from __future__ import annotations

import types
from src import caching_layer


def test_caching_layer_prefers_cache_and_invalidates(monkeypatch):
    class _FakeSession:
        def __init__(self):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            self.calls += 1
            return [{"id": "r1", "text": "T", "section": "S"}]

    class _FakeGraph:
        def __init__(self):
            self.session_obj = _FakeSession()

        def session(self):
            return self.session_obj

    kg = types.SimpleNamespace(_graph=_FakeGraph())

    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, value):
            self.store[key] = value

        def keys(self, pattern):
            return list(self.store.keys())

        def delete(self, *keys):
            removed = 0
            for k in keys:
                if k in self.store:
                    removed += 1
                    self.store.pop(k, None)
            return removed

    monkeypatch.setattr(caching_layer, "redis", object())
    fake_redis = _FakeRedis()
    layer = caching_layer.CachingLayer(kg, redis_client=fake_redis)

    first = layer.get_rules_cached("summary")
    second = layer.get_rules_cached("summary")
    assert first == second == [{"id": "r1", "text": "T", "section": "S"}]
    assert kg._graph.session_obj.calls == 1  # cache hit skips graph
    assert layer.invalidate_cache() == 1
