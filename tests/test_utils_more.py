from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.infra import utils
from src.core.models import WorkflowResult


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


def test_safe_json_parse_list_with_raise():
    with pytest.raises(ValueError):
        utils.safe_json_parse("[1,2,3]", raise_on_error=True)


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


def test_parse_raw_candidates_auto_split_three():
    raw = "alpha\n\n---\n\nbravo text\n\n---\n\ncharlie content"
    parsed = utils.parse_raw_candidates(raw)
    assert parsed["A"].startswith("alpha")
    assert parsed["B"].startswith("bravo")
    assert parsed["C"].startswith("charlie")


@pytest.mark.asyncio
async def test_load_checkpoint_ignores_bad_lines(tmp_path: Path):
    path = tmp_path / "checkpoint.jsonl"
    valid = WorkflowResult(
        turn_id=1,
        query="good",
        evaluation=None,
        best_answer="A",
        rewritten_answer="B",
        cost=0.0,
        final_output=None,
        success=True,
        error_message=None,
    ).model_dump()
    # mix of invalid and valid payloads
    path.write_text(
        "\n".join(
            [
                "",  # blank
                "not json",  # invalid
                json.dumps({"turn_id": 2}),  # missing fields
                json.dumps(valid),
            ]
        ),
        encoding="utf-8",
    )

    records = await utils.load_checkpoint(path)
    assert list(records.keys()) == ["good"]
    assert isinstance(records["good"], WorkflowResult)
