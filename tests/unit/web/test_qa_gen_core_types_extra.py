"""Extra tests for qa_gen_core.types to boost branch coverage."""

from __future__ import annotations

from src.web.routers.qa_gen_core.types import get_query_intent, normalize_qtype


def test_normalize_qtype_mapping_and_default() -> None:
    assert normalize_qtype("target_short") == "target"
    assert normalize_qtype("reasoning") == "reasoning"
    assert normalize_qtype("unknown") == "explanation"


def test_get_query_intent_target_short_with_dedup_and_exclusion() -> None:
    intent = get_query_intent(
        "target_short",
        previous_queries=["Q1", "Q2"],
        explanation_answer="설명문 내용입니다.",
    )
    assert "간단한 사실 확인 질문" in intent
    assert "중복 방지" in intent
    assert "설명문 내용 제외" in intent
    assert "단일 포커스" in intent


def test_get_query_intent_target_long_with_previous_queries() -> None:
    intent = get_query_intent("target_long", previous_queries=["A", "B"])
    assert "핵심 요점을 묻는 질문" in intent
    assert "중복 방지" in intent


def test_get_query_intent_reasoning_and_explanation_defaults() -> None:
    assert "추론" in get_query_intent("reasoning")
    assert "전체 내용 설명" in get_query_intent("global_explanation")
    # Unknown qtype still returns the common clause
    unknown_intent = get_query_intent("factual")
    assert "단일 포커스" in unknown_intent
