"""Tests for structured(JSON) answer rendering in postprocess_answer."""

from __future__ import annotations

from src.web.utils import postprocess_answer


def test_postprocess_renders_structured_explanation_json() -> None:
    structured = '{"intro":"도입입니다.","sections":[{"title":"실적 요약","items":[{"label":"매출","text":"전년 대비 증가했습니다."},{"label":"이익","text":"수익성이 개선되었습니다."}]}],"conclusion":"핵심은 성장세입니다"}'

    result = postprocess_answer(structured, "global_explanation")
    assert "**실적 요약**" in result
    assert "- **매출**: 전년 대비 증가했습니다" in result
    assert "요약하면, 핵심은 성장세입니다" in result


def test_postprocess_renders_structured_reasoning_json() -> None:
    structured = '{"intro":"핵심 결론은 개선입니다.","sections":[{"title":"주요 근거","items":[{"label":"요인 1","text":"비용 구조가 개선되었습니다."},{"label":"요인 2","text":"수주가 확대되었습니다."}]}],"conclusion":"개선 흐름이 이어질 가능성이 큽니다"}'

    result = postprocess_answer(structured, "reasoning")
    assert result.startswith("핵심 결론은 개선입니다")
    assert "**주요 근거**" in result
    assert "- **요인 1**: 비용 구조가 개선되었습니다" in result
    assert "종합하면, 개선 흐름이 이어질 가능성이 큽니다" in result


def test_postprocess_parses_json_inside_code_fence() -> None:
    structured = """```json
{"intro":"도입.","sections":[{"title":"핵심","items":[{"label":"A","text":"B"},{"label":"C","text":"D"}]}],"conclusion":"끝"}
```"""
    result = postprocess_answer(structured, "reasoning")
    assert "**핵심**" in result
    assert "- **A**: B" in result
