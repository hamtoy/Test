from __future__ import annotations

import types
from typing import Any

import pytest

from src import compare_documents
from src import health_check


def test_compare_documents_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(EnvironmentError):
        compare_documents.require_env("MISSING_ENV")

    class _CompareSession:
        def __enter__(self) -> "_CompareSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, query: str, **_kwargs: Any) -> list[dict[str, Any]]:
            if "ORDER BY total_blocks" in query:
                return [
                    {
                        "title": "Doc A",
                        "total_blocks": 2,
                        "types": ["heading", "paragraph"],
                    },
                    {"title": "Doc B", "total_blocks": 1, "types": ["paragraph"]},
                ]
            return [{"content": "공통 내용", "pages": ["Doc A", "Doc B"]}]

    driver = types.SimpleNamespace(session=lambda: _CompareSession())
    structures = compare_documents.compare_structure(driver)
    commons = compare_documents.find_common_content(driver, limit=1)
    assert structures[0]["title"] == "Doc A"
    assert commons[0][1] == ["Doc A", "Doc B"]


def test_health_check_with_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set required environment variables for Neo4j
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")

    # Import the actual health module to patch the right namespace
    from src.infra import health as infra_health

    class _HealthSession:
        def __enter__(self) -> "_HealthSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> types.SimpleNamespace:
            return types.SimpleNamespace(single=lambda: 1)

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _HealthSession())
    )
    assert infra_health.check_neo4j_connection(fake_kg) is True  # type: ignore[arg-type]

    monkeypatch.setattr(infra_health, "check_neo4j_connection", lambda *_a, **_k: True)
    report = health_check.health_check()
    assert report["status"] == "healthy"


def test_compare_documents_main_flow(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "user")
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")

    # Import the actual document_compare module to patch the right namespace
    from src.analysis import document_compare

    class _Session:
        def __enter__(self) -> "_Session":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
            if "collect(DISTINCT b.type)" in query:
                return [
                    {
                        "title": "Page A",
                        "total_blocks": 2,
                        "types": ["heading", "paragraph"],
                    },
                    {"title": "Page B", "total_blocks": 1, "types": ["paragraph"]},
                ]
            return [
                {"content": "content text long enough", "pages": ["Page A", "Page B"]}
            ]

    class _Driver:
        def session(self) -> _Session:
            return _Session()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        document_compare,
        "GraphDatabase",
        types.SimpleNamespace(driver=lambda uri, auth: _Driver()),
    )
    compare_documents.main()
    out = capsys.readouterr().out
    assert "Page A" in out
    assert "공통으로 등장하는 내용" in out
