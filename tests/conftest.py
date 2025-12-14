import json
import os
import sys
import types
import warnings
from pathlib import Path
from typing import Any, List, Optional, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

# Register fixtures from tests.fixtures package
pytest_plugins = ["tests.fixtures"]

# Mock API key for testing: AIza + 35 zeros = 39 characters total (valid format)
MOCK_GEMINI_API_KEY = "AIza" + "0" * 35

# Set GEMINI_API_KEY before any module imports that might trigger AppConfig validation.
# This is necessary because worker.py creates config = AppConfig() at module level,
# which happens during test collection (before fixtures run).
os.environ.setdefault("GEMINI_API_KEY", MOCK_GEMINI_API_KEY)

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
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure AppConfig validation passes with valid mock values."""
    monkeypatch.setenv("GEMINI_API_KEY", MOCK_GEMINI_API_KEY)
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-flash-latest")


@pytest.fixture(autouse=True)
def clear_neo4j_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Neo4j drivers are not implicitly created during tests."""
    for var in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    return None


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
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

    def __init__(self, responses: Optional[List[Any]] = None) -> None:
        self._responses = list(responses) if responses else []

    def __enter__(self) -> "MockSession":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc: Optional[BaseException],
        tb: Optional[Any],
    ) -> None:
        pass

    def run(self, *args: Any, **kwargs: Any) -> List[Any]:
        if self._responses:
            result = self._responses.pop(0)
            return result if isinstance(result, list) else [result]
        return []


class MockDriver:
    """Common Neo4j driver mock."""

    def __init__(self, session: Optional[Any] = None) -> None:
        if isinstance(session, list):
            self._session: MockSession = MockSession(session)
        else:
            self._session = session or MockSession()

    def session(self) -> MockSession:
        return self._session

    def close(self) -> None:
        pass


class MockKnowledgeGraph:
    """Common KnowledgeGraph mock."""

    def __init__(self, session: Optional[Any] = None) -> None:
        self._graph = MockDriver(session)


@pytest.fixture
def mock_neo4j_session() -> MockSession:
    """Neo4j session mock fixture."""
    return MockSession()


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session: MockSession) -> MockDriver:
    """Neo4j driver mock fixture."""
    return MockDriver(mock_neo4j_session)


@pytest.fixture
def mock_knowledge_graph(mock_neo4j_session: MockSession) -> MockKnowledgeGraph:
    """KnowledgeGraph mock fixture."""
    return MockKnowledgeGraph(mock_neo4j_session)


@pytest.fixture
def mock_gemini_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock Gemini API client for testing."""
    mock_client = MagicMock()

    # Mock generate response
    mock_response = MagicMock()
    mock_response.text = "Mocked response text"
    mock_response.usage_metadata = MagicMock(
        prompt_token_count=10,
        candidates_token_count=20,
        total_token_count=30,
    )

    mock_client.generate_content.return_value = mock_response
    mock_client.generate_content_async = AsyncMock(return_value=mock_response)

    # Mock model info
    mock_client.model_name = "gemini-1.5-flash"
    mock_client._model = MagicMock()

    return mock_client


@pytest.fixture
def mock_genai(
    monkeypatch: pytest.MonkeyPatch, mock_gemini_client: MagicMock
) -> MagicMock:
    """Mock google.generativeai module."""
    mock_genai = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_gemini_client._model
    mock_genai.configure = MagicMock()

    monkeypatch.setattr(
        "google.generativeai.GenerativeModel", mock_genai.GenerativeModel
    )
    monkeypatch.setattr("google.generativeai.configure", mock_genai.configure)

    return mock_genai


@pytest.fixture(scope="function", autouse=True)
def isolate_registry() -> Any:
    """각 테스트마다 레지스트리 격리."""
    from src.web.service_registry import get_registry, reset_registry_for_test

    registry = get_registry()

    # 현재 상태 백업
    original_state = registry.get_state_for_test()

    # 테스트 전 초기화
    reset_registry_for_test()

    yield

    # 테스트 후 복원
    registry.restore_state_for_test(original_state)
