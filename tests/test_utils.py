import pytest

from src.utils import clean_markdown_code_block, safe_json_parse


def test_clean_markdown_code_block_strips_block():
    text = "```json\n{\"A\":1}\n```"
    assert clean_markdown_code_block(text) == '{"A":1}'


def test_safe_json_parse_nested_dict_and_list():
    payload = """
    {
        "outer": {
            "inner": [{"rewritten_answer": "value"}]
        }
    }
    """
    assert safe_json_parse(payload, "rewritten_answer") == "value"


def test_safe_json_parse_non_json_returns_none():
    assert safe_json_parse("not json") is None
