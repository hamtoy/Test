"""Tests for answer truncation behavior."""

from __future__ import annotations

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parents[1]))

from src.web.utils import apply_answer_limits


def test_truncation_extended() -> None:
    """Test that truncation works correctly with extended answers."""
    # Test case 1: Long reasoning answer
    long_text = "This is a very long reasoning answer. " * 50
    result = apply_answer_limits(long_text, "reasoning")
    assert len(result) < len(long_text)
    assert result.endswith(".")

    # Test case 2: Long explanation answer
    long_explanation = "This is a detailed explanation. " * 100
    result = apply_answer_limits(long_explanation, "global_explanation")
    # Explanation type doesn't have word limits but should have period
    assert result.endswith(".") or result.endswith("...")

    # Test case 3: Target short answer - no truncation needed
    short_target = "Short answer"
    result = apply_answer_limits(short_target, "target")
    assert result == short_target  # No period added for short target

    # Test case 4: Target long answer
    long_target = "This is a longer target answer with more detail. " * 20
    result = apply_answer_limits(long_target, "target")
    assert len(result) < len(long_target)
    assert result.endswith(".")

    # Test case 5: Ellipsis handling for reasoning
    reasoning_with_ellipsis = "Some reasoning text..."
    result = apply_answer_limits(reasoning_with_ellipsis, "reasoning")
    assert result.endswith(".")
    assert not result.endswith("...")

    # Test case 6: Ellipsis preservation for explanation
    explanation_with_ellipsis = "Some explanation text..."
    result = apply_answer_limits(explanation_with_ellipsis, "global_explanation")
    assert result.endswith("...")


@pytest.mark.parametrize(
    "qtype,text,expected_ending",
    [
        ("reasoning", "Test...", "."),
        ("global_explanation", "Test...", "..."),
        ("target", "Short", "Short"),
    ],
)
def test_qtype_specific_punctuation(
    qtype: str, text: str, expected_ending: str
) -> None:
    """Test qtype-specific punctuation handling."""
    result = apply_answer_limits(text, qtype)
    assert result.endswith(expected_ending)
def test_truncation_extended():
    # Extended text:
    # 1. First sentence (contains decimal 3. 7%)
    # 2. Second sentence (contains decimal 3. 9%, 27. 5) -> "혼재된 양상을 보였습니다."
    # 3. Third sentence ("그러나 ... 16.")
    # 4. Fourth sentence ("추가 문장 1")
    # 5. Fifth sentence ("추가 문장 2")
    # 6. Sixth sentence ("추가 문장 3") -> Should be kept (limit is 5? No, limit is 5 sentences).
    # Wait, reasoning limit is 5.
    # So sentences 1, 2, 3, 4, 5 kept.
    # Sentence 6 dropped.

    text = (
        "2월 고용보고서에서 실업률이 전월 3. 7%에서 3. 9%로 상승했으며, "
        "비농업취업자 수는 시장 예상인 20만명을 웃도는 27. 5만명을 기록하여 "
        "혼재된 양상을 보였습니다. 그러나 과거 1월과 12월 두 달간의 취업자 수가 총 16. "
        "이것은 세번째 문장입니다. 이것은 네번째 문장입니다. 이것은 다섯번째 문장입니다. "
        "이것은 여섯번째 문장입니다."
    )

    print(f"Input text len: {len(text)}")
    res = apply_answer_limits(text, "reasoning")
    print(f"Result text len: {len(res)}")
    print(f"Result: {res}")

    # Verification
    # If the bug exists (naive split):
    # It splits on "3. 7", "3. 9", "27. 5".
    # Sentences > 5 quickly.
    # It cuts at "총 16." (approx).
    # So "세번째 문장" will be MISSING.

    if "세번째 문장" in res:
        print("SUCCESS: '세번째 문장' found. Sentence splitting logic is robust.")
    else:
        print("FAILURE: '세번째 문장' missing. Truncated too early.")

    if "다섯번째 문장" in res:
        print("SUCCESS: '다섯번째 문장' found. (Limit is 5)")
    else:
        print("FAILURE: '다섯번째 문장' missing.")


if __name__ == "__main__":
    test_truncation_extended()
