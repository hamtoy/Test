import types
from typing import Any, Optional

import pytest
from neo4j.exceptions import Neo4jError

from src import health_check


class _BadGraph:
    def session(self) -> "_BadGraph":
        return self

    def __enter__(self) -> "_BadGraph":
        return self

    def __exit__(self, exc_type: Optional[type], exc: Optional[BaseException], tb: Any) -> None:
        pass

    def run(self, *args: Any, **kwargs: Any) -> None:
        raise Neo4jError("boom")

    def single(self) -> None:
        return None


def test_check_neo4j_connection_false_on_error() -> None:
    kg = types.SimpleNamespace(_graph=_BadGraph())
    assert health_check.check_neo4j_connection(kg) is False  # type: ignore[arg-type]


def test_health_check_report(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set required environment variables for Neo4j
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")

    # Import the actual health module to patch the right namespace
    from src.infra import health as infra_health

    monkeypatch.setattr(infra_health, "check_neo4j_connection", lambda kg=None: True)
    res = health_check.health_check()
    assert res["status"] == "healthy"
    assert res["neo4j"] is True
