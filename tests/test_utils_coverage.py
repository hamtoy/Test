from __future__ import annotations

import pytest
import types
from src import compare_documents
from src import health_check


def test_compare_documents_helpers(monkeypatch):
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(EnvironmentError):
        compare_documents.require_env("MISSING_ENV")

    class _CompareSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
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


def test_health_check_with_stub(monkeypatch):
    class _HealthSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return types.SimpleNamespace(single=lambda: 1)

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _HealthSession())
    )
    assert health_check.check_neo4j_connection(fake_kg) is True

    monkeypatch.setattr(health_check, "check_neo4j_connection", lambda *_a, **_k: True)
    report = health_check.health_check()
    assert report["status"] == "healthy"
