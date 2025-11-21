import pytest
import json
from src.data_loader import validate_candidates, load_input_data
from src.exceptions import ValidationFailedError


def test_validate_candidates_success():
    candidates = {"A": "content", "B": "content", "C": "content"}
    validate_candidates(candidates)  # Should not raise


def test_validate_candidates_missing_keys():
    candidates = {"A": "content", "B": "content"}
    with pytest.raises(ValidationFailedError, match="Candidates missing required keys"):
        validate_candidates(candidates)


def test_validate_candidates_empty_content():
    candidates = {"A": "", "B": "content", "C": "content"}
    with pytest.raises(ValidationFailedError, match="has empty content"):
        validate_candidates(candidates)


@pytest.mark.asyncio
async def test_load_input_data_success(tmp_path):
    ocr_file = tmp_path / "ocr.txt"
    ocr_file.write_text("ocr content", encoding="utf-8")

    cand_file = tmp_path / "cand.json"
    cand_data = {"A": "a", "B": "b", "C": "c"}
    cand_file.write_text(json.dumps(cand_data), encoding="utf-8")

    ocr_text, candidates = await load_input_data(tmp_path, "ocr.txt", "cand.json")

    assert ocr_text == "ocr content"
    assert candidates == cand_data


@pytest.mark.asyncio
async def test_load_input_data_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="OCR file missing"):
        await load_input_data(tmp_path, "missing_ocr.txt", "cand.json")


@pytest.mark.asyncio
async def test_load_input_data_empty_ocr(tmp_path):
    ocr_file = tmp_path / "ocr.txt"
    ocr_file.write_text("", encoding="utf-8")
    cand_file = tmp_path / "cand.json"
    cand_file.touch()

    with pytest.raises(ValueError, match="File is empty"):
        await load_input_data(tmp_path, "ocr.txt", "cand.json")


@pytest.mark.asyncio
async def test_load_input_data_raw_text_fallback(tmp_path):
    ocr_file = tmp_path / "ocr.txt"
    ocr_file.write_text("ocr content", encoding="utf-8")

    cand_file = tmp_path / "cand.txt"
    cand_content = """
A: Answer A
B: Answer B
C: Answer C
"""
    cand_file.write_text(cand_content, encoding="utf-8")

    ocr_text, candidates = await load_input_data(tmp_path, "ocr.txt", "cand.txt")

    assert candidates["A"] == "Answer A"
    assert candidates["B"] == "Answer B"
    assert candidates["C"] == "Answer C"
