"""Tests for markdown preservation in postprocess_answer.

Based on guide.csv rules:
- CSV 규칙에서 허용하는 마크다운: **bold**, 1. 2. 3., - 항목
- CSV 규칙에서 금지하는 마크다운: *italic*, ### 제목
- postprocess_answer()는 허용된 마크다운만 유지하고 금지된 마크다운은 제거
"""

import pytest

from src.web.utils import postprocess_answer


@pytest.mark.parametrize(
    "qtype,input_text,expected",
    [
        # ✅ 허용된 마크다운 유지: **bold**
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
        # ❌ 금지된 마크다운 제거: ### 헤더
        (
            "reasoning",
            "### 미-중 갈등 고조\n전일 한국 증시는...",
            "미-중 갈등 고조\n전일 한국 증시는.",
        ),
        (
            "global_explanation",
            "## 투자 의견\n### 목표주가\n내용입니다",
            "투자 의견\n목표주가\n내용입니다.",
        ),
        # ❌ 금지된 마크다운 제거: *italic*
        (
            "reasoning",
            "*강조* 텍스트입니다",
            "강조 텍스트입니다.",
        ),
        (
            "global_explanation",
            "이것은 *중요한* 내용입니다",
            "이것은 중요한 내용입니다.",
        ),
        # ✅ **bold** 보호하면서 *italic* 제거
        (
            "reasoning",
            "**핵심**과 *부가* 정보",
            "**핵심**과 부가 정보.",
        ),
        (
            "global_explanation",
            "**미-중 갈등 고조**\n*투자 심리 위축*",
            "**미-중 갈등 고조**\n투자 심리 위축.",
        ),
        # ✅ 복합 테스트: ### 헤더와 *italic* 동시 제거, **bold** 유지
        (
            "reasoning",
            "### 제목\n**핵심**: *부가* 정보\n- 항목1\n- 항목2",
            "제목\n**핵심**: 부가 정보\n- 항목1\n- 항목2.",
        ),
        # 기본 정리 테스트 - 연속된 빈 줄 정리
        ("reasoning", "텍스트\n\n\n\n여러 줄바꿈", "텍스트\n\n\n여러 줄바꿈."),
        # target 타입도 동일하게 처리
        ("target", "**핵심**입니다", "**핵심**입니다"),
        ("target_short", "### 제목\n- **항목1**: 내용", "제목\n- **항목1**: 내용"),
        ("target_long", "*강조* 텍스트", "강조 텍스트"),
        # 코드 블록은 제거됨
        ("reasoning", "```python\ncode```\n텍스트", "텍스트."),
        # 링크는 텍스트만 남김
        ("global_explanation", "[링크 텍스트](http://example.com)", "링크 텍스트."),
        # 실제 시나리오: CSV 예시와 유사한 형식
        (
            "global_explanation",
            "### 미-중 갈등 고조 및 투자 심리 위축\n"
            "전일 한국 증시의 약세를...\n\n"
            "**주식 전망 및 인사이트**\n"
            "1. 영업이익률 회복 흐름\n"
            "    - 동국제약의 *영업이익률*이 상승...",
            "미-중 갈등 고조 및 투자 심리 위축\n"
            "전일 한국 증시의 약세를...\n\n"
            "**주식 전망 및 인사이트**\n"
            "1. 영업이익률 회복 흐름\n"
            "    - 동국제약의 영업이익률이 상승...",
        ),
    ],
)
def test_markdown_processing(qtype: str, input_text: str, expected: str) -> None:
    """마크다운 처리 검증 - CSV 규칙과 일치.

    허용: **bold**, 1. 2. 3., - 항목
    제거: *italic*, ### 제목
    """
    result = postprocess_answer(input_text, qtype)
    assert result == expected


def test_italic_without_bold() -> None:
    """*italic*만 있는 경우 제거 검증."""
    input_text = "이것은 *강조*된 텍스트입니다"
    result = postprocess_answer(input_text, "reasoning")
    assert result == "이것은 강조된 텍스트입니다."
    assert "*" not in result


def test_bold_preservation() -> None:
    """**bold**가 손상없이 유지되는지 검증."""
    input_text = "**핵심 키워드**는 강조됩니다"
    result = postprocess_answer(input_text, "global_explanation")
    assert "**핵심 키워드**" in result
    assert result == "**핵심 키워드**는 강조됩니다."


def test_mixed_markdown_removal() -> None:
    """여러 금지 마크다운이 혼재된 경우 모두 제거."""
    input_text = "### 제목\n*italic* 그리고 **bold** 유지"
    result = postprocess_answer(input_text, "reasoning")
    assert "###" not in result
    assert "*italic*" not in result
    assert "**bold**" in result
    assert result == "제목\nitalic 그리고 **bold** 유지."


def test_multiple_headers_removal() -> None:
    """여러 레벨의 헤더 모두 제거."""
    input_text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\n내용"
    result = postprocess_answer(input_text, "global_explanation")
    assert "#" not in result
    assert result == "H1\nH2\nH3\nH4\nH5\nH6\n내용."


def test_unmatched_asterisks_removal() -> None:
    """짝이 맞지 않는 별표도 제거."""
    input_text = "이것은 *홑별표 텍스트"
    result = postprocess_answer(input_text, "reasoning")
    # 짝이 맞지 않는 홑별표는 제거됨
    assert "*" not in result
    assert "홑별표" in result
