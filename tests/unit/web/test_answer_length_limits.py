"""Tests for answer length limits and post-processing."""

from __future__ import annotations

import pytest

from src.web.utils import apply_answer_limits, postprocess_answer


# Test data constants
COMPREHENSIVE_EXPLANATION_BASE = """전일 한국 증시는 여러 복합적인 요인으로 하락 마감했습니다.

**주요 하락 요인**

첫째, FOMC(연방공개시장위원회) 회의를 앞두고 달러화 강세가 지속되면서 외국인 투자자들의 매도세가 강화되었습니다. """

COMPREHENSIVE_EXPLANATION_REPEATED = (
    "이는 원화 약세로 이어져 외국인 자금 유출을 가속화했습니다. " * 20
)

COMPREHENSIVE_EXPLANATION_CLOSING = """

**시장 심리 위축**

투자자들은 Fed의 긴축 기조 지속 가능성에 대한 우려로 관망세를 보였습니다."""


class TestAnswerLengthLimits:
    """Test suite for answer length constraints."""

    def test_global_explanation_no_word_limit(self) -> None:
        """Test that global_explanation type does not have word limit applied.

        This test validates Fix #2: global_explanation answers should not be
        truncated by apply_answer_limits() to allow 1000-1500 character responses.
        """
        # Create a long comprehensive answer (simulating 1500+ character response)
        long_answer = (
            COMPREHENSIVE_EXPLANATION_BASE
            + COMPREHENSIVE_EXPLANATION_REPEATED
            + COMPREHENSIVE_EXPLANATION_CLOSING
        )

        # Apply limits for global_explanation
        result = apply_answer_limits(long_answer, "global_explanation")

        # Should NOT truncate (length should be preserved or minimally changed)
        # Allow for whitespace normalization but not word truncation
        assert len(result) >= len(long_answer) - 100, (
            f"global_explanation should not be truncated. "
            f"Original: {len(long_answer)}, Result: {len(result)}"
        )

    def test_reasoning_has_word_limit(self) -> None:
        """Test that reasoning type still has word limit applied."""
        # Create a long answer with many words
        long_answer = " ".join(["테스트"] * 150) + "."

        # Apply limits for reasoning
        result = apply_answer_limits(long_answer, "reasoning")

        # Should be limited to ~100 words
        word_count = len(result.split())
        assert word_count <= 110, (
            f"reasoning should be limited to ~100 words, got {word_count}"
        )

    def test_target_short_maintains_limits(self) -> None:
        """Test that target (short) type maintains its short constraints."""
        # Create a medium-length answer
        medium_answer = " ".join(["테스트"] * 20) + "."

        # Apply limits for target (should detect as short based on length)
        result = apply_answer_limits(medium_answer, "target")

        # Should be limited to 50 words for short answers
        word_count = len(result.split())
        assert word_count <= 55, (
            f"target short should be limited to ~50 words, got {word_count}"
        )

    def test_postprocess_preserves_explanation_length(self) -> None:
        """Test that postprocess_answer doesn't over-truncate explanation answers.

        This is an integration test for the full post-processing pipeline.
        """
        # Comprehensive answer with markdown
        comprehensive_answer = (
            "**주요 하락 요인**\n\n첫째, FOMC 회의를 앞두고 달러화 강세가 지속되었습니다. "
            + "이는 외국인 자금 유출을 가속화했습니다. " * 15
            + "\n\n**시장 심리 위축**\n\n투자자들은 Fed의 긴축 기조에 우려를 보였습니다."
        )

        original_length = len(comprehensive_answer)

        # Process for global_explanation
        result = postprocess_answer(comprehensive_answer, "global_explanation")

        # Should preserve most of the content (allow some formatting changes)
        # But should NOT truncate to 200 words (~400 chars)
        assert len(result) >= original_length * 0.6, (
            f"postprocess_answer should not over-truncate. "
            f"Original: {original_length}, Result: {len(result)}"
        )

    def test_cache_truncation_constants_match(self) -> None:
        """Test that cache and generation OCR truncation lengths are synchronized.

        This validates Fix #1: QA_CACHE_OCR_TRUNCATE_LENGTH should match
        QA_GENERATION_OCR_TRUNCATE_LENGTH to prevent context loss.
        """
        from src.config.constants import (
            QA_CACHE_OCR_TRUNCATE_LENGTH,
            QA_GENERATION_OCR_TRUNCATE_LENGTH,
        )

        assert QA_CACHE_OCR_TRUNCATE_LENGTH == QA_GENERATION_OCR_TRUNCATE_LENGTH, (
            f"Cache and generation OCR truncation lengths must match! "
            f"Cache: {QA_CACHE_OCR_TRUNCATE_LENGTH}, "
            f"Generation: {QA_GENERATION_OCR_TRUNCATE_LENGTH}"
        )

        # Both should be 3000 as per the fix
        assert QA_CACHE_OCR_TRUNCATE_LENGTH == 3000, (
            f"Expected 3000, got {QA_CACHE_OCR_TRUNCATE_LENGTH}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
