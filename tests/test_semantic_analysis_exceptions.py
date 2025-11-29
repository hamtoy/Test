from __future__ import annotations

import logging
from typing import Any, Optional

import pytest
from neo4j.exceptions import Neo4jError

import src.analysis.semantic as sa


def test_main_handles_neo4j_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Import the actual semantic module to patch the right namespace
    from src.analysis import semantic as analysis_semantic

    monkeypatch.setattr(analysis_semantic, "require_env", lambda name: "x")

    def _raise(*_a: Any, **_k: Any) -> None:
        raise Neo4jError("boom")

    monkeypatch.setattr(analysis_semantic.GraphDatabase, "driver", _raise)  # type: ignore[attr-defined]
    with pytest.raises(SystemExit):
        sa.main()


def test_main_no_blocks_returns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Import the actual semantic module to patch the right namespace
    from src.analysis import semantic as analysis_semantic

    monkeypatch.setattr(analysis_semantic, "require_env", lambda name: "x")

    class _Session:
        def __enter__(self) -> "_Session":
            return self

        def __exit__(
            self, exc_type: Optional[type], exc: Optional[BaseException], tb: Any
        ) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> list[Any]:
            return []

    class _Driver:
        def __init__(self) -> None:
            self.closed = False

        def session(self) -> _Session:
            return _Session()

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(
        analysis_semantic.GraphDatabase,  # type: ignore[attr-defined]
        "driver",
        lambda *a, **k: _Driver(),
    )
    monkeypatch.setattr(analysis_semantic, "fetch_blocks", lambda driver: [])

    with caplog.at_level(logging.INFO):
        sa.main()

    assert any("처리할 Block이 없습니다." in rec.message for rec in caplog.records)
