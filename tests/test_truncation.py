"""Tests for answer truncation behavior."""

from __future__ import annotations

import pytest

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
