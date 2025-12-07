"""Tests for markdown handling consistency in postprocess_answer.

Based on guide.csv rules:
- target: Plain text only (remove all markdown)
- explanation/reasoning: Structural markdown only (headings/lists), content is plain text
"""

import pytest

from src.web.utils import postprocess_answer


@pytest.mark.parametrize(
    "qtype,input_text,expected",
    [
        # target: 마크다운 모두 제거 (guide.csv 규칙)
        ("target", "**핵심**입니다", "핵심입니다"),
        ("target", "- **항목1**: 내용", "항목1: 내용"),
        ("target", "1. *방법*: 설명", "1. 방법: 설명"),
        # explanation/reasoning: Bullets removed, paragraphs combined
        # Note: Structural markdown (headings/lists) handling is done at prompt level
        # Postprocessing focuses on cleaning and paragraph formatting
        ("global_explanation", "**주요 포인트**\n첫 번째 설명", "주요 포인트 첫 번째 설명."),
        ("reasoning", "- 항목1: 설명\n- 항목2: 설명", "항목1: 설명 항목2: 설명."),
        # Additional test: Verify bold removal works in target
        ("target", "*강조* 텍스트", "강조 텍스트"),
    ],
)
def test_markdown_consistency(qtype: str, input_text: str, expected: str) -> None:
    """guide.csv 규칙에 따른 마크다운 처리 검증."""
    result = postprocess_answer(input_text, qtype)
    assert result == expected
