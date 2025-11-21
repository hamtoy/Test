import json
from pathlib import Path

import pytest

from src.data_loader import load_input_data
from src.exceptions import ValidationFailedError


@pytest.mark.asyncio
async def test_load_input_data_valid_candidates(tmp_path: Path):
    base_dir = tmp_path
    (base_dir / "input_ocr.txt").write_text("sample ocr text", encoding="utf-8")
    (base_dir / "input_candidates.json").write_text(
        json.dumps({"A": "answer a", "B": "answer b", "C": "answer c"}),
        encoding="utf-8",
    )

    ocr_text, candidates = await load_input_data(base_dir, "input_ocr.txt", "input_candidates.json")

    assert ocr_text == "sample ocr text"
    assert candidates["A"] == "answer a"
    assert set(candidates.keys()) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_load_input_data_missing_candidate_key(tmp_path: Path):
    base_dir = tmp_path
    (base_dir / "input_ocr.txt").write_text("ocr text", encoding="utf-8")
    (base_dir / "input_candidates.json").write_text(
        json.dumps({"A": "a", "B": "b"}), encoding="utf-8"
    )

    with pytest.raises(ValidationFailedError):
        await load_input_data(base_dir, "input_ocr.txt", "input_candidates.json")


@pytest.mark.asyncio
async def test_load_input_data_empty_candidate_content(tmp_path: Path):
    base_dir = tmp_path
    (base_dir / "input_ocr.txt").write_text("ocr text", encoding="utf-8")
    (base_dir / "input_candidates.json").write_text(
        json.dumps({"A": "a", "B": "  ", "C": "c"}), encoding="utf-8"
    )

    with pytest.raises(ValidationFailedError):
        await load_input_data(base_dir, "input_ocr.txt", "input_candidates.json")
