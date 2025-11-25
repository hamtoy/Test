import json

import pytest
import warnings
import sys
import types
from typing import Any, cast

# Neo4j sync driver emits a noisy deprecation warning when GC closes a driver.
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r"Relying on Driver's destructor to close the session is deprecated.*",
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"neo4j\.?_sync\.driver",
)


# Minimal langchain stubs for modules that are not installed in CI.
# This must run before any src modules are imported in tests.
lc_base_module = sys.modules.setdefault(
    "langchain.callbacks.base", types.ModuleType("langchain.callbacks.base")
)
cast(Any, lc_base_module).BaseCallbackHandler = type("BaseCallbackHandler", (), {})

callbacks_module = sys.modules.setdefault(
    "langchain.callbacks", types.ModuleType("langchain.callbacks")
)
cast(Any, callbacks_module).base = lc_base_module

langchain_module = sys.modules.setdefault("langchain", types.ModuleType("langchain"))
cast(Any, langchain_module).callbacks = callbacks_module


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure AppConfig validation passes with valid mock values."""
    # AIza + 35 characters = 39 characters total
    mock_key = "AIza" + "0" * 35
    monkeypatch.setenv("GEMINI_API_KEY", mock_key)
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")


@pytest.fixture(autouse=True)
def clear_neo4j_env(monkeypatch):
    """Ensure Neo4j drivers are not implicitly created during tests."""
    for var in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    return None


@pytest.fixture
def temp_data_dir(tmp_path):
    """Provide isolated input directory with sample OCR and candidate files."""
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()

    (input_dir / "ocr.txt").write_text("Sample OCR", encoding="utf-8")
    candidates = {"A": "Answer A", "B": "Answer B", "C": "Answer C"}
    (input_dir / "cand.json").write_text(
        json.dumps(candidates, ensure_ascii=False), encoding="utf-8"
    )
    return input_dir


class MockSession:
    """Common Neo4j session mock."""

    def __init__(self, responses=None):
        self._responses = list(responses) if responses else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        if self._responses:
            result = self._responses.pop(0)
            return result if isinstance(result, list) else [result]
        return []


class MockDriver:
    """Common Neo4j driver mock."""

    def __init__(self, session=None):
        if isinstance(session, list):
            self._session = MockSession(session)
        else:
            self._session = session or MockSession()

    def session(self):
        return self._session

    def close(self):
        pass


class MockKnowledgeGraph:
    """Common KnowledgeGraph mock."""

    def __init__(self, session=None):
        self._graph = MockDriver(session)


@pytest.fixture
def mock_neo4j_session():
    """Neo4j session mock fixture."""
    return MockSession()


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    """Neo4j driver mock fixture."""
    return MockDriver(mock_neo4j_session)


@pytest.fixture
def mock_knowledge_graph(mock_neo4j_session):
    """KnowledgeGraph mock fixture."""
    return MockKnowledgeGraph(mock_neo4j_session)
