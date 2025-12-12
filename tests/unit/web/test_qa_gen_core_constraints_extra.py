"""Extra tests for qa_gen_core.constraints."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.web.routers.qa_gen_core.constraints import (
    build_constraints_text,
    load_constraints_from_kg,
    validate_constraint_conflicts,
)


def test_load_constraints_returns_empty_when_kg_none() -> None:
    result = load_constraints_from_kg(None, "explanation")
    assert result.query_constraints == []
    assert result.answer_constraints == []
    assert result.formatting_rules == []


def test_load_constraints_filters_invalid_items_and_categories() -> None:
    kg = MagicMock()
    kg.get_constraints_for_query_type.return_value = [
        {"category": "query", "description": "Q rule", "priority": 10},
        {"category": "answer", "description": "A rule", "priority": 5},
        {"category": "both", "description": "Both rule", "priority": 1},
        "not-a-dict",
        123,
    ]
    kg.get_formatting_rules_for_query_type.return_value = [
        {"description": "fmt1"},
        {"text": "fmt2"},
        "bad",
    ]

    result = load_constraints_from_kg(kg, "explanation")
    assert any(c.get("description") == "Q rule" for c in result.query_constraints)
    assert any(c.get("description") == "A rule" for c in result.answer_constraints)
    assert any(c.get("description") == "Both rule" for c in result.query_constraints)
    assert any(c.get("description") == "Both rule" for c in result.answer_constraints)
    assert result.formatting_rules == ["fmt1", "fmt2"]


def test_build_constraints_text_sorts_by_priority() -> None:
    text = build_constraints_text(
        [
            {"description": "low", "priority": 1},
            {"description": "high", "priority": 10},
        ],
    )
    first_line = text.splitlines()[0]
    assert "high" in first_line


def test_validate_constraint_conflicts_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    answer_constraints: list[dict[str, Any]] = [
        {"description": "3문단 각 30단어 이상", "priority": 10},
    ]
    caplog.set_level("WARNING")
    validate_constraint_conflicts(
        answer_constraints,
        length_constraint="[길이 제약] 최대 50단어",
        normalized_qtype="explanation",
    )
    assert any("제약 충돌 감지" in rec.message for rec in caplog.records)
