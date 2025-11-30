"""Additional tests for src/processing/loader.py to improve coverage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import AppConfig
from src.config.exceptions import ValidationFailedError
from src.processing.loader import load_input_data, reload_data_if_needed


@pytest.mark.asyncio
async def test_load_input_data_candidate_file_missing(tmp_path: Path) -> None:
    """Test that FileNotFoundError is raised when candidate file is missing."""
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    # Candidate file does NOT exist

    with pytest.raises(FileNotFoundError, match="Candidate file missing"):
        await load_input_data(base_dir, "ocr.txt", "missing_candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_candidate_file_empty(tmp_path: Path) -> None:
    """Test that ValueError is raised when candidate file is empty."""
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text("", encoding="utf-8")

    # Empty file raises ValueError from load_file_async
    with pytest.raises(ValueError, match="File is empty"):
        await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_candidate_file_whitespace_only(tmp_path: Path) -> None:
    """Test that ValueError is raised when candidate file has only whitespace."""
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text("   \n\t  ", encoding="utf-8")

    # Whitespace only raises ValueError from load_file_async
    with pytest.raises(ValueError, match="File is empty"):
        await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_json_empty_dict(tmp_path: Path) -> None:
    """Test fallback when JSON is valid but empty dict.

    Empty dict triggers raw text parsing fallback, which treats the entire
    text as Candidate A, resulting in validation failure for missing B, C.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text("{}", encoding="utf-8")

    # Fallback treats "{}" as raw text -> Candidate A only -> missing B, C
    with pytest.raises(ValidationFailedError, match="Candidates missing required keys"):
        await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_json_invalid_type(tmp_path: Path) -> None:
    """Test fallback when JSON is valid but wrong type (list instead of dict).

    List type triggers raw text parsing fallback.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text('["A", "B", "C"]', encoding="utf-8")

    # List type triggers raw text parsing fallback -> missing keys
    with pytest.raises(ValidationFailedError, match="Candidates missing required keys"):
        await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_unparseable_format(tmp_path: Path) -> None:
    """Test error when neither JSON nor raw text format works.

    Content without A:, B:, C: patterns falls back to treating entire text
    as Candidate A, resulting in validation failure for missing B, C.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    # Content that doesn't match JSON or raw text format (A:, B:, C:)
    (base_dir / "candidates.txt").write_text(
        "This is just random text\nwithout proper format", encoding="utf-8"
    )

    with pytest.raises(ValidationFailedError, match="Candidates missing required keys"):
        await load_input_data(base_dir, "ocr.txt", "candidates.txt")


@pytest.mark.asyncio
async def test_reload_data_if_needed(tmp_path: Path) -> None:
    """Test reload_data_if_needed function."""
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text(
        json.dumps({"A": "answer a", "B": "answer b", "C": "answer c"}),
        encoding="utf-8",
    )

    mock_config = MagicMock(spec=AppConfig)
    mock_config.input_dir = base_dir

    ocr_text, candidates = await reload_data_if_needed(
        mock_config, "ocr.txt", "candidates.json", interactive=True
    )

    assert ocr_text == "sample ocr text"
    assert candidates["A"] == "answer a"


@pytest.mark.asyncio
async def test_load_input_data_json_type_error(tmp_path: Path) -> None:
    """Test that TypeError during JSON parsing is handled.

    Falls back to raw text parsing.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text(
        '{"A": "a", "B": "b", "C": "c"}', encoding="utf-8"
    )

    with patch("src.processing.loader.json.loads") as mock_loads:
        mock_loads.side_effect = TypeError("mock type error")
        # Falls back to raw text parsing -> treats entire JSON text as A -> missing B, C
        with pytest.raises(
            ValidationFailedError, match="Candidates missing required keys"
        ):
            await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_json_value_error(tmp_path: Path) -> None:
    """Test that ValueError during JSON parsing is handled.

    Falls back to raw text parsing.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text(
        '{"A": "a", "B": "b", "C": "c"}', encoding="utf-8"
    )

    with patch("src.processing.loader.json.loads") as mock_loads:
        mock_loads.side_effect = ValueError("mock value error")
        # Falls back to raw text parsing -> treats entire JSON text as A -> missing B, C
        with pytest.raises(
            ValidationFailedError, match="Candidates missing required keys"
        ):
            await load_input_data(base_dir, "ocr.txt", "candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_json_unexpected_error(tmp_path: Path) -> None:
    """Test that unexpected Exception during JSON parsing is handled.

    Falls back to raw text parsing.
    """
    base_dir = tmp_path
    (base_dir / "ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "candidates.json").write_text(
        '{"A": "a", "B": "b", "C": "c"}', encoding="utf-8"
    )

    with patch("src.processing.loader.json.loads") as mock_loads:
        mock_loads.side_effect = RuntimeError("unexpected mock error")
        # Falls back to raw text parsing -> treats entire JSON text as A -> missing B, C
        with pytest.raises(
            ValidationFailedError, match="Candidates missing required keys"
        ):
            await load_input_data(base_dir, "ocr.txt", "candidates.json")
