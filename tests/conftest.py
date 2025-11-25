import json

import pytest
import warnings

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
