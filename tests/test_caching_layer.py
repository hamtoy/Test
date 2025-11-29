import json
import types

from src.caching.layer import CachingLayer


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, cypher, **params):  # noqa: ARG002
        for r in self.rows:
            yield r


class _FakeGraph:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeSession(self._rows)


def test_get_rules_cached_without_redis(monkeypatch):
    rows = [{"id": "1", "text": "t1", "section": "s1"}]
    kg = types.SimpleNamespace(_graph=_FakeGraph(rows))
    layer = CachingLayer(kg=kg, redis_client=None)  # type: ignore[arg-type]

    rules = layer.get_rules_cached("explanation")
    assert rules == [{"id": "1", "text": "t1", "section": "s1"}]


def test_get_rules_cached_with_redis(monkeypatch):
    rows = [{"id": "2", "text": "t2", "section": "s2"}]
    kg = types.SimpleNamespace(_graph=_FakeGraph(rows))

    class _FakeRedis:
        def __init__(self):
            self.store = {}
            self.deleted = 0

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, value):
            self.store[key] = value

        def keys(self, pattern):
            return list(self.store.keys())

        def delete(self, *keys):
            self.deleted += len(keys)
            for k in keys:
                self.store.pop(k, None)
            return self.deleted

    r = _FakeRedis()
    layer = CachingLayer(kg=kg, redis_client=r)  # type: ignore[arg-type]
    # Force redis usage even if redis module is absent
    layer.redis = r

    # First call populates cache
    rules = layer.get_rules_cached("explanation")
    assert rules[0]["id"] == "2"
    # Cached fetch uses stored JSON
    cached = json.dumps([{"id": "3", "text": "t3", "section": "s3"}])
    r.store["rules:explanation"] = cached
    rules2 = layer.get_rules_cached("explanation")
    assert rules2[0]["id"] == "3"

    deleted = layer.invalidate_cache()
    assert deleted == 1
