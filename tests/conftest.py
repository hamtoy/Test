import json

import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Ensure AppConfig validation passes with valid mock values."""
    # AIza + 35 characters = 39 characters total
    mock_key = "AIza" + "0" * 35
    monkeypatch.setenv("GEMINI_API_KEY", mock_key)
    monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")


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
