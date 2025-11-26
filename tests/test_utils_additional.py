import json
from pathlib import Path

import pytest

from src import utils
from src.core.models import WorkflowResult


def test_safe_json_parse_errors():
    # JSONDecodeError -> None
    assert utils.safe_json_parse("not-json") is None

    # raise_on_error True -> ValueError for non-JSON format
    with pytest.raises(ValueError):
        utils.safe_json_parse("not-json", raise_on_error=True)

    # JSON array should be rejected unless raise_on_error
    assert utils.safe_json_parse("[1,2,3]") is None
    with pytest.raises(ValueError):
        utils.safe_json_parse("[1,2,3]", raise_on_error=True)


def test_write_cache_stats_trims(tmp_path: Path):
    path = tmp_path / "cache.jsonl"
    # Seed with four entries
    for i in range(4):
        utils.write_cache_stats(path, max_entries=10, entry={"n": i})

    # Add new entry with small max_entries to trigger trim
    utils.write_cache_stats(path, max_entries=3, entry={"n": 99})

    lines = path.read_text(encoding="utf-8").splitlines()
    data = [json.loads(x) for x in lines]
    assert len(data) == 3
    # Keep the last 3 entries only
    assert [d["n"] for d in data] == [2, 3, 99]


@pytest.mark.asyncio
async def test_checkpoint_roundtrip(tmp_path: Path):
    path = tmp_path / "checkpoint.jsonl"
    wf1 = WorkflowResult(
        turn_id=1,
        query="q1",
        evaluation=None,
        best_answer="a1",
        rewritten_answer="r1",
    )
    wf2 = WorkflowResult(
        turn_id=2,
        query="q2",
        evaluation=None,
        best_answer="a2",
        rewritten_answer="r2",
    )

    await utils.append_checkpoint(path, wf1)
    await utils.append_checkpoint(path, wf2)

    loaded = await utils.load_checkpoint(path)
    assert loaded["q1"].best_answer == "a1"
    assert loaded["q2"].rewritten_answer == "r2"


def test_safe_json_parse_target_key():
    payload = {"a": {"b": "c"}}
    text = json.dumps(payload)
    assert utils.safe_json_parse(text, target_key="b") == "c"
    # missing key returns None
    assert utils.safe_json_parse(text, target_key="missing") is None
