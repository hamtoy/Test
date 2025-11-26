from __future__ import annotations

import logging

import pytest
from neo4j.exceptions import Neo4jError

import src.semantic_analysis as sa


def test_main_handles_neo4j_error(monkeypatch):
    # Import the actual semantic module to patch the right namespace
    from src.analysis import semantic as analysis_semantic

    monkeypatch.setattr(analysis_semantic, "require_env", lambda name: "x")

    def _raise(*_a, **_k):
        raise Neo4jError("boom")

    monkeypatch.setattr(analysis_semantic.GraphDatabase, "driver", _raise)
    with pytest.raises(SystemExit):
        sa.main()


def test_main_no_blocks_returns(monkeypatch, caplog):
    # Import the actual semantic module to patch the right namespace
    from src.analysis import semantic as analysis_semantic

    monkeypatch.setattr(analysis_semantic, "require_env", lambda name: "x")

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return []

    class _Driver:
        def __init__(self):
            self.closed = False

        def session(self):
            return _Session()

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        analysis_semantic.GraphDatabase, "driver", lambda *a, **k: _Driver()
    )
    monkeypatch.setattr(analysis_semantic, "fetch_blocks", lambda driver: [])

    with caplog.at_level(logging.INFO):
        sa.main()

    assert any("처리할 Block이 없습니다." in rec.message for rec in caplog.records)
