from __future__ import annotations

import types
from typing import Any

import pytest

from src.config.utils import require_env
from src.graph import QAGraphBuilder


def test_require_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(EnvironmentError):
        require_env("NEO4J_URI")


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._data_queue: list[object] = []

    def __enter__(self) -> "_Session":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    def run(self, query: str, **params: Any) -> Any:
        self.calls.append((query.strip(), params))
        if self._data_queue:
            return self._data_queue.pop(0)
        return types.SimpleNamespace(data=lambda: [])

    def data(self) -> list[Any]:
        return []


class _Driver:
    def __init__(self) -> None:
        self.session_obj = _Session()

    def session(self) -> _Session:
        return self.session_obj

    def close(self) -> None:
        return None


def test_create_schema_and_query_types(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = _Driver()
    builder = QAGraphBuilder.__new__(QAGraphBuilder)
    builder.driver = driver  # type: ignore[assignment]
    builder.logger = types.SimpleNamespace(info=lambda *a, **k: None)  # type: ignore[assignment]

    builder.create_schema_constraints()
    assert driver.session_obj.calls  # ran multiple constraints

    builder.extract_query_types()
    assert any("MERGE (q:QueryType" in q for q, _ in driver.session_obj.calls)


def test_extract_rules_no_headings(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = _Driver()
    session = driver.session_obj
    session._data_queue.append(types.SimpleNamespace(data=lambda: []))  # headings empty
    builder = QAGraphBuilder.__new__(QAGraphBuilder)
    builder.driver = driver  # type: ignore[assignment]
    builder.logger = types.SimpleNamespace(info=lambda *a, **k: None)  # type: ignore[assignment]
    builder.extract_rules_from_notion()  # should not raise even with no data
