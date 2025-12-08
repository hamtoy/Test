"""Tests for markdown preservation in postprocess_answer.

Based on guide.csv rules:
- CSV 규칙에서는 마크다운 형식으로 답변을 생성하도록 명시
- postprocess_answer()는 마크다운을 유지하고 기본 정리만 수행
"""

import pytest

from src.web.utils import postprocess_answer


@pytest.mark.parametrize(
    "qtype,input_text,expected",
    [
        # 마크다운 유지 테스트 - reasoning/global_explanation는 period 추가
        (
            "reasoning",
            "**핵심 포인트:**\n- 첫 번째 항목\n- 두 번째 항목",
            "**핵심 포인트:**\n- 첫 번째 항목\n- 두 번째 항목.",
        ),
        (
            "global_explanation",
            "**주요 분석:**\n\n1. 항목 1\n2. 항목 2",
            "**주요 분석:**\n\n1. 항목 1\n2. 항목 2.",
        ),
        # 기본 정리 테스트 - 연속된 빈 줄 정리
        ("reasoning", "텍스트\n\n\n\n여러 줄바꿈", "텍스트\n\n\n여러 줄바꿈."),
        # target 타입도 마크다운 유지 (period는 apply_answer_limits에서 처리)
        ("target", "**핵심**입니다", "**핵심**입니다"),
        ("target_short", "- **항목1**: 내용", "- **항목1**: 내용"),
        ("target_long", "*강조* 텍스트", "*강조* 텍스트"),
        # 코드 블록은 제거됨
        ("reasoning", "```python\ncode```\n텍스트", "텍스트."),
        # 링크는 텍스트만 남김
        ("global_explanation", "[링크 텍스트](http://example.com)", "링크 텍스트."),
    ],
)
def test_markdown_preservation(qtype: str, input_text: str, expected: str) -> None:
    """마크다운 유지 검증 - CSV 규칙과 일치."""
    result = postprocess_answer(input_text, qtype)
    assert result == expected
