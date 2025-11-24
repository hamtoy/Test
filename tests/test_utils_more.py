from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import utils


@pytest.mark.asyncio
async def test_load_file_async_missing_and_empty(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        await utils.load_file_async(missing)

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        await utils.load_file_async(empty)


def test_safe_json_parse_variants(caplog):
    assert utils.safe_json_parse("") is None
    assert utils.safe_json_parse("not-json") is None
    assert utils.safe_json_parse("[1,2,3]") is None
    assert utils.safe_json_parse("{}", target_key="missing") is None

    data = {"a": {"b": 1}}
    text = json.dumps(data)
    assert utils.safe_json_parse(text, target_key="b") == 1

    with pytest.raises(ValueError):
        utils.safe_json_parse("", raise_on_error=True)


def test_write_cache_stats_trims_and_caps(tmp_path: Path):
    path = tmp_path / "stats.jsonl"
    # prepopulate more than cap
    entries = [{"id": i} for i in range(5)]
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

    utils.write_cache_stats(path, max_entries=3, entry={"id": 99})

    lines = path.read_text(encoding="utf-8").splitlines()
    # capped at 3, newest appended
    assert len(lines) == 3
    assert json.loads(lines[-1])["id"] == 99


def test_parse_raw_candidates_with_fallback(caplog):
    text = "Hello world"
    parsed = utils.parse_raw_candidates(text)
    assert parsed == {"A": "Hello world"}

    structured = utils.parse_raw_candidates("A: first\n\nB: second")
    assert structured == {"A": "first", "B": "second"}
