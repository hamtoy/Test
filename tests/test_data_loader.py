import pytest
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
async def test_load_input_data_success(temp_data_dir):
    ocr_text, candidates = await load_input_data(temp_data_dir, "ocr.txt", "cand.json")

    assert ocr_text == "Sample OCR"
    assert candidates == {"A": "Answer A", "B": "Answer B", "C": "Answer C"}


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


@pytest.mark.asyncio
async def test_load_input_data_with_utf8_bom(tmp_path):
    """Test that files with UTF-8 BOM are handled correctly (Windows compat)."""
    # Write OCR file with UTF-8 BOM
    ocr_file = tmp_path / "ocr.txt"
    ocr_file.write_bytes(b"\xef\xbb\xbfSample OCR with BOM")

    # Write JSON file with UTF-8 BOM
    cand_file = tmp_path / "cand.json"
    json_content = '{"A": "Answer A", "B": "Answer B", "C": "Answer C"}'
    cand_file.write_bytes(b"\xef\xbb\xbf" + json_content.encode("utf-8"))

    ocr_text, candidates = await load_input_data(tmp_path, "ocr.txt", "cand.json")

    assert ocr_text == "Sample OCR with BOM"
    assert candidates == {"A": "Answer A", "B": "Answer B", "C": "Answer C"}
