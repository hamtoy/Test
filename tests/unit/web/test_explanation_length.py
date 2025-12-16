"""Tests for explanation type answer length constraints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Sample comprehensive answer for testing (simulates expected output)
SAMPLE_COMPREHENSIVE_ANSWER = """전일 한국 증시는 여러 복합적인 요인으로 하락 마감했습니다.

**주요 하락 요인**

첫째, FOMC(연방공개시장위원회) 회의를 앞두고 달러화 강세가 지속되면서 외국인 투자자들의 매도세가 강화되었습니다. 이는 원화 약세로 이어져 외국인 자금 유출을 가속화했습니다.

둘째, 미국 증시의 조정 국면이 아시아 시장에 영향을 미쳤습니다. 특히 기술주를 중심으로 한 나스닥 지수의 하락이 국내 IT 섹터에 부정적 영향을 주었습니다.

**시장 심리 위축**

투자자들은 Fed의 긴축 기조 지속 가능성에 대한 우려로 관망세를 보였습니다. 이에 따라 거래량이 감소하고 변동성이 확대되는 모습을 보였습니다.

**결과적으로**

KOSPI 지수는 전일 대비 1.14% 하락한 2,450포인트로 마감했으며, KOSDAQ은 2.35% 하락한 850포인트를 기록했습니다. 외국인과 기관 투자자 모두 순매도를 기록하며 시장 전반의 약세를 이끌었습니다."""


@pytest.mark.asyncio
class TestExplanationAnswerLength:
    """Tests for explanation answer length constraint."""

    async def test_explanation_type_has_length_constraint(self) -> None:
        """Test that explanation type generates length constraint instructions."""
        from src.web.routers.qa_generation import generate_single_qa

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["테스트 설명 질의"])
        mock_agent.rewrite_best_answer = AsyncMock(
            return_value=SAMPLE_COMPREHENSIVE_ANSWER
        )

        with (
            patch(
                "src.web.routers.qa_gen_core.generator.get_cached_kg", return_value=None
            ),
            patch("src.web.routers.qa_gen_core.generator._get_kg", return_value=None),
            patch(
                "src.web.routers.qa_gen_core.generator._get_pipeline", return_value=None
            ),
            patch(
                "src.web.routers.qa_gen_core.generator.semantic_answer_cache.get",
                return_value=None,
            ),
            patch("src.web.routers.qa_gen_core.generator.semantic_answer_cache.set"),
            patch(
                "src.web.routers.qa_gen_core.generator.postprocess_answer",
                return_value=SAMPLE_COMPREHENSIVE_ANSWER,
            ),
        ):
            await generate_single_qa(
                mock_agent,
                "OCR 텍스트 샘플",
                "global_explanation",
            )

            # Verify rewrite_best_answer was called
            assert mock_agent.rewrite_best_answer.called

            # Get the call arguments
            call_args = mock_agent.rewrite_best_answer.call_args

            # Check that length_constraint parameter was passed
            if call_args.kwargs:
                length_constraint = call_args.kwargs.get("length_constraint", "")
                # Verify it contains comprehensive length guidance
                assert "1000-1500자" in length_constraint or "최소" in length_constraint
                assert "5-8개 문단" in length_constraint or "문단" in length_constraint

    async def test_explanation_answer_length_validation_warning(self) -> None:
        """Test that short explanation answers trigger a warning."""
        from src.web.routers.qa_generation import generate_single_qa

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["테스트 질의"])

        # Short answer (should trigger warning) - very short compared to OCR
        short_answer = "전일 한국 증시는 FOMC 회의를 앞두고 하락했습니다."

        mock_agent.rewrite_best_answer = AsyncMock(return_value=short_answer)

        # Long OCR text to trigger the length warning (60% of this = ~150 chars)
        long_ocr = "테스트 " * 50  # ~250 chars

        with (
            patch(
                "src.web.routers.qa_gen_core.generator.get_cached_kg", return_value=None
            ),
            patch("src.web.routers.qa_gen_core.generator._get_kg", return_value=None),
            patch(
                "src.web.routers.qa_gen_core.generator._get_pipeline", return_value=None
            ),
            patch(
                "src.web.routers.qa_gen_core.generator.semantic_answer_cache.get",
                return_value=None,
            ),
            patch("src.web.routers.qa_gen_core.generator.semantic_answer_cache.set"),
            patch(
                "src.web.routers.qa_gen_core.generator.postprocess_answer",
                return_value=short_answer,
            ),
            # Patch validation.logger where warning is actually called
            patch("src.web.routers.qa_gen_core.validation.logger") as mock_logger,
        ):
            await generate_single_qa(
                mock_agent,
                long_ocr,
                "global_explanation",
            )

            # Should log warning for short answer
            warning_called = any(
                "Answer too short" in str(call)
                for call in mock_logger.warning.call_args_list
            )
            assert warning_called, "Expected warning for short explanation answer"

    async def test_target_short_no_length_increase(self) -> None:
        """Test that target_short type maintains its short length constraint."""
        from src.web.routers.qa_generation import generate_single_qa

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["테스트 질의"])

        # Short answer (expected for target_short)
        short_answer = "네, KOSPI 지수는 1.14% 하락했습니다."

        mock_agent.rewrite_best_answer = AsyncMock(return_value=short_answer)

        with (
            patch(
                "src.web.routers.qa_gen_core.generator.get_cached_kg", return_value=None
            ),
            patch("src.web.routers.qa_gen_core.generator._get_kg", return_value=None),
            patch(
                "src.web.routers.qa_gen_core.generator._get_pipeline", return_value=None
            ),
            patch(
                "src.web.routers.qa_gen_core.generator.semantic_answer_cache.get",
                return_value=None,
            ),
            patch("src.web.routers.qa_gen_core.generator.semantic_answer_cache.set"),
            patch(
                "src.web.routers.qa_gen_core.generator.postprocess_answer",
                return_value=short_answer,
            ),
            patch("src.web.routers.qa_gen_core.generator.logger") as mock_logger,
        ):
            result = await generate_single_qa(
                mock_agent,
                "OCR 텍스트",
                "target_short",
            )

            # Should NOT log warning for short answer in target_short type
            if mock_logger.warning.called:
                warning_messages = [
                    call[0][0] for call in mock_logger.warning.call_args_list
                ]
                # Filter out unrelated warnings
                length_warnings = [
                    msg for msg in warning_messages if "Answer too short" in msg
                ]
                assert not length_warnings, (
                    "Should not warn about length for target_short"
                )

            # Verify the answer is returned
            assert result["answer"] == short_answer
            assert result["type"] == "target_short"
