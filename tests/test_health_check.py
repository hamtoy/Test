import types

from neo4j.exceptions import Neo4jError

from src import health_check


class _BadGraph:
    def session(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        raise Neo4jError("boom")

    def single(self):
        return None


def test_check_neo4j_connection_false_on_error():
    kg = types.SimpleNamespace(_graph=_BadGraph())
    assert health_check.check_neo4j_connection(kg) is False


def test_health_check_report(monkeypatch):
    monkeypatch.setattr(health_check, "check_neo4j_connection", lambda kg=None: True)
    res = health_check.health_check()
    assert res["status"] == "healthy"
    assert res["neo4j"] is True
