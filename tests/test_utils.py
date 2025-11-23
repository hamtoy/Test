import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.utils import (
    load_file_async,
    parse_raw_candidates,
    clean_markdown_code_block,
    safe_json_parse,
)


@pytest.mark.asyncio
async def test_load_file_async_success():
    mock_content = "test content"
    mock_file = MagicMock()
    mock_file.__aenter__.return_value.read = AsyncMock(return_value=mock_content)
    mock_file.__aexit__.return_value = None

    with patch("aiofiles.open", return_value=mock_file):
        result = await load_file_async("dummy_path")
        assert result == mock_content


@pytest.mark.asyncio
async def test_load_file_async_empty():
    mock_file = MagicMock()
    mock_file.__aenter__.return_value.read = AsyncMock(return_value="")
    mock_file.__aexit__.return_value = None

    with (
        patch("aiofiles.open", return_value=mock_file),
        pytest.raises(ValueError, match="File is empty"),
    ):
        await load_file_async("dummy_path")


@pytest.mark.asyncio
async def test_load_file_async_not_found():
    with (
        patch("aiofiles.open", side_effect=FileNotFoundError),
        pytest.raises(FileNotFoundError, match="Critical file missing"),
    ):
        await load_file_async("dummy_path")


def test_parse_raw_candidates_valid():
    text = """
A: First answer
B: Second answer
C: Third answer
"""
    expected = {"A": "First answer", "B": "Second answer", "C": "Third answer"}
    assert parse_raw_candidates(text) == expected


def test_parse_raw_candidates_fallback():
    text = "Just some text without structure."
    expected = {"A": "Just some text without structure."}
    assert parse_raw_candidates(text) == expected


def test_clean_markdown_code_block_json():
    text = '```json\n{"key": "value"}\n```'
    assert clean_markdown_code_block(text) == '{"key": "value"}'


def test_clean_markdown_code_block_plain():
    text = '```\n{"key": "value"}\n```'
    assert clean_markdown_code_block(text) == '{"key": "value"}'


def test_clean_markdown_code_block_no_block():
    text = '{"key": "value"}'
    assert clean_markdown_code_block(text) == '{"key": "value"}'


def test_safe_json_parse_success():
    text = '{"key": "value"}'
    assert safe_json_parse(text) == {"key": "value"}


def test_safe_json_parse_with_markdown():
    text = '```json\n{"key": "value"}\n```'
    assert safe_json_parse(text) == {"key": "value"}


def test_safe_json_parse_invalid_json():
    text = "{invalid json}"
    assert safe_json_parse(text) is None


def test_safe_json_parse_target_key():
    text = '{"key": "value", "nested": {"target": "got it"}}'
    assert safe_json_parse(text, target_key="target") == "got it"


def test_safe_json_parse_target_key_not_found():
    text = '{"key": "value"}'
    assert safe_json_parse(text, target_key="missing") is None


def test_safe_json_parse_raise_on_error():
    text = "{invalid json}"
    with pytest.raises(Exception):
        safe_json_parse(text, raise_on_error=True)
