from __future__ import annotations

import types

import pytest

from src.graph_schema_builder import QAGraphBuilder, require_env


def test_require_env_missing(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(EnvironmentError):
        require_env("NEO4J_URI")


class _Session:
    def __init__(self):
        self.calls = []
        self._data_queue = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **params):
        self.calls.append((query.strip(), params))
        if self._data_queue:
            return self._data_queue.pop(0)
        return types.SimpleNamespace(data=lambda: [])

    def data(self):
        return []


class _Driver:
    def __init__(self):
        self.session_obj = _Session()

    def session(self):
        return self.session_obj

    def close(self):
        return None


def test_create_schema_and_query_types(monkeypatch):
    driver = _Driver()
    builder = QAGraphBuilder.__new__(QAGraphBuilder)
    builder.driver = driver
    builder.logger = types.SimpleNamespace(info=lambda *a, **k: None)

    builder.create_schema_constraints()
    assert driver.session_obj.calls  # ran multiple constraints

    builder.extract_query_types()
    assert any("MERGE (q:QueryType" in q for q, _ in driver.session_obj.calls)


def test_extract_rules_no_headings(monkeypatch):
    driver = _Driver()
    session = driver.session_obj
    session._data_queue.append(types.SimpleNamespace(data=lambda: []))  # headings empty
    builder = QAGraphBuilder.__new__(QAGraphBuilder)
    builder.driver = driver
    builder.logger = types.SimpleNamespace(info=lambda *a, **k: None)
    builder.extract_rules_from_notion()  # should not raise even with no data
