import json
from pathlib import Path

from scripts.build_session import SessionContext, build_session
from checks.validate_session import validate_turns
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_ctx(name: str) -> SessionContext:
    data = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    return SessionContext(**data)


def turn_types(turns: Any) -> Any:
    return [t.type for t in turns]


def test_table_context_no_violation() -> None:
    ctx = load_ctx("context_table.json")
    turns = build_session(ctx)
    result = validate_turns(turns, ctx)
    assert result["ok"]
    assert turn_types(turns)[0] in ("summary", "explanation")
    # ensure calc not overused
    assert (
        ctx.used_calc_query_count
        + sum(int(getattr(t, "calc_used", False)) for t in turns)
        <= 1
    )


def test_low_text_prefers_explanation_and_three_turns() -> None:
    ctx = load_ctx("context_low_text.json")
    turns = build_session(ctx)
    assert len(turns) == 3
    assert turn_types(turns)[0] == "explanation"
    result = validate_turns(turns, ctx)
    assert result["ok"]


def test_calc_used_context_blocks_extra_calc() -> None:
    ctx = load_ctx("context_calc_used.json")
    turns = build_session(ctx)
    result = validate_turns(turns, ctx)
    assert result["ok"]
    # calc already consumed; targets should not push total over 1
    assert (
        ctx.used_calc_query_count
        + sum(int(getattr(t, "calc_used", False)) for t in turns)
        <= 1
    )
