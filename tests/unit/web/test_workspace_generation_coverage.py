"""Comprehensive test coverage for src/web/routers/workspace_generation.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from src.web.routers.workspace_generation import (
    _evaluate_answer_quality,
    _generate_lats_answer,
    _lats_evaluate_answer,
    api_generate_answer_from_query,
    api_generate_query_from_answer,
)


class TestGenerateAnswerFromQuery:
    """Test api_generate_answer_from_query endpoint."""

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_kg")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    @patch("src.web.routers.workspace_generation.RuleLoader")
    async def test_generate_answer_success(
        self,
        mock_rule_loader_cls: Mock,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_kg: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test successful answer generation."""
        mock_agent = AsyncMock()
        mock_agent.rewrite_best_answer = AsyncMock(return_value="정확한 답변입니다.")
        mock_get_agent.return_value = mock_agent

        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR 텍스트"

        mock_rule_loader = MagicMock()
        mock_rule_loader.get_rules_for_type.return_value = ["규칙1", "규칙2"]
        mock_rule_loader_cls.return_value = mock_rule_loader

        body = {
            "query": "테스트 질문",
            "query_type": "explanation",
        }

        result = await api_generate_answer_from_query(body)

        assert "query" in result
        assert "answer" in result
        assert result["answer"] == "정확한 답변입니다."

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    async def test_generate_answer_agent_not_initialized(
        self, mock_get_agent: Mock
    ) -> None:
        """Test error when agent is not initialized."""
        mock_get_agent.return_value = None

        body = {"query": "질문"}

        with pytest.raises(HTTPException) as exc_info:
            await api_generate_answer_from_query(body)

        assert exc_info.value.status_code == 500
        assert "Agent 초기화 실패" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_kg")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    @patch("src.web.routers.workspace_generation.RuleLoader")
    async def test_generate_answer_timeout(
        self,
        mock_rule_loader_cls: Mock,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_kg: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test timeout during answer generation."""
        mock_agent = AsyncMock()
        mock_agent.rewrite_best_answer = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_get_agent.return_value = mock_agent

        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        mock_config = MagicMock()
        mock_config.workspace_timeout = 1
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR"

        mock_rule_loader = MagicMock()
        mock_rule_loader.get_rules_for_type.return_value = []
        mock_rule_loader_cls.return_value = mock_rule_loader

        body = {"query": "질문"}

        with pytest.raises(HTTPException) as exc_info:
            await api_generate_answer_from_query(body)

        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_kg")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    @patch("src.web.routers.workspace_generation.RuleLoader")
    @patch("src.web.routers.workspace_generation.find_violations")
    async def test_generate_answer_with_violations_retry(
        self,
        mock_find_violations: Mock,
        mock_rule_loader_cls: Mock,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_kg: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test retry logic when violations are detected."""
        mock_agent = AsyncMock()
        # First call has violations, second call is clean
        mock_agent.rewrite_best_answer = AsyncMock(
            side_effect=["- 불릿 답변", "정상 답변"]
        )
        mock_get_agent.return_value = mock_agent

        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR"

        mock_rule_loader = MagicMock()
        mock_rule_loader.get_rules_for_type.return_value = []
        mock_rule_loader_cls.return_value = mock_rule_loader

        # First call has violations, second call is clean
        mock_find_violations.side_effect = [[{"type": "bullet"}], []]

        body = {"query": "질문"}

        result = await api_generate_answer_from_query(body)

        # Should have called rewrite twice
        assert mock_agent.rewrite_best_answer.call_count == 2
        assert result["answer"] == "정상 답변"

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_kg")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    @patch("src.web.routers.workspace_generation.RuleLoader")
    @patch("src.web.routers.workspace_generation.find_violations")
    async def test_generate_answer_max_retries_exceeded(
        self,
        mock_find_violations: Mock,
        mock_rule_loader_cls: Mock,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_kg: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test max retries exceeded still returns answer."""
        mock_agent = AsyncMock()
        mock_agent.rewrite_best_answer = AsyncMock(return_value="- 계속 불릿")
        mock_get_agent.return_value = mock_agent

        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR"

        mock_rule_loader = MagicMock()
        mock_rule_loader.get_rules_for_type.return_value = []
        mock_rule_loader_cls.return_value = mock_rule_loader

        # Always has violations
        mock_find_violations.return_value = [{"type": "bullet"}]

        body = {"query": "질문"}

        result = await api_generate_answer_from_query(body)

        # Should return last answer even with violations
        assert "answer" in result


class TestGenerateQueryFromAnswer:
    """Test api_generate_query_from_answer endpoint."""

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    async def test_generate_query_success(
        self,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test successful query generation."""
        mock_agent = AsyncMock()
        mock_agent.generate_query = AsyncMock(return_value=["생성된 질문은?"])
        mock_get_agent.return_value = mock_agent

        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR 텍스트"

        body = {"answer": "이것은 답변입니다."}

        result = await api_generate_query_from_answer(body)

        assert "query" in result
        assert result["query"] == "생성된 질문은?"

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    async def test_generate_query_agent_not_initialized(
        self, mock_get_agent: Mock
    ) -> None:
        """Test error when agent is not initialized."""
        mock_get_agent.return_value = None

        body = {"answer": "답변"}

        with pytest.raises(HTTPException) as exc_info:
            await api_generate_query_from_answer(body)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    async def test_generate_query_timeout(
        self,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test timeout during query generation."""
        mock_agent = AsyncMock()
        mock_agent.generate_query = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_get_agent.return_value = mock_agent

        mock_config = MagicMock()
        mock_config.workspace_timeout = 1
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR"

        body = {"answer": "답변"}

        with pytest.raises(HTTPException) as exc_info:
            await api_generate_query_from_answer(body)

        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._get_config")
    @patch("src.web.routers.workspace_generation.load_ocr_text")
    async def test_generate_query_empty_result(
        self,
        mock_load_ocr: Mock,
        mock_get_config: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test fallback when query generation returns empty."""
        mock_agent = AsyncMock()
        mock_agent.generate_query = AsyncMock(return_value=[])
        mock_get_agent.return_value = mock_agent

        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_get_config.return_value = mock_config

        mock_load_ocr.return_value = "OCR"

        body = {"answer": "답변"}

        result = await api_generate_query_from_answer(body)

        assert result["query"] == "질문 생성 실패"


class TestGenerateLATSAnswer:
    """Test _generate_lats_answer function."""

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._evaluate_answer_quality")
    @patch("src.web.routers.workspace_generation.strip_output_tags")
    @patch("src.web.routers.workspace_generation.LATS_WEIGHTS_PRESETS")
    async def test_generate_lats_answer_success(
        self,
        mock_weights_presets: Mock,
        mock_strip: Mock,
        mock_evaluate: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test LATS answer generation with multiple strategies."""
        from src.web.routers.workspace_generation import AnswerQualityWeights

        # Setup weights
        test_weights = AnswerQualityWeights(min_length=10)
        mock_weights_presets.get.return_value = test_weights

        mock_agent = MagicMock()
        mock_agent._create_generative_model = MagicMock()

        # Create proper mock responses with strip() method
        mock_responses = []
        for text in [
            "숫자 중심 답변입니다",
            "트렌드 중심 답변입니다",
            "비교 중심 답변입니다",
        ]:
            mock_resp = MagicMock()
            mock_resp.strip.return_value = text
            mock_responses.append(mock_resp)

        mock_agent._call_api_with_retry = AsyncMock(side_effect=mock_responses)
        mock_get_agent.return_value = mock_agent

        # Strip returns the text as-is
        mock_strip.side_effect = lambda x: x

        # Make all candidates qualify with scores >= 0.6
        mock_evaluate.side_effect = [0.75, 0.80, 0.70]

        query = "매출 분석"
        ocr_text = "2023년 매출 100억"
        query_type = "explanation"

        answer, meta = await _generate_lats_answer(query, ocr_text, query_type)

        # Should have best answer
        assert answer in [
            "숫자 중심 답변입니다",
            "트렌드 중심 답변입니다",
            "비교 중심 답변입니다",
        ]
        assert meta["candidates"] >= 1

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    @patch("src.web.routers.workspace_generation._evaluate_answer_quality")
    async def test_generate_lats_answer_all_low_quality(
        self,
        mock_evaluate: Mock,
        mock_get_agent: Mock,
    ) -> None:
        """Test LATS when all candidates are low quality."""
        mock_agent = MagicMock()
        mock_agent._create_generative_model = MagicMock()
        mock_agent._call_api_with_retry = AsyncMock(
            return_value=MagicMock(strip=MagicMock(return_value="저품질 답변"))
        )
        mock_get_agent.return_value = mock_agent

        # All candidates below threshold
        mock_evaluate.return_value = 0.5

        query = "질문"
        ocr_text = "데이터"
        query_type = "explanation"

        answer, meta = await _generate_lats_answer(query, ocr_text, query_type)

        assert answer == ""
        assert meta["reason"] == "all_low_quality"

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_agent")
    async def test_generate_lats_answer_no_agent(
        self,
        mock_get_agent: Mock,
    ) -> None:
        """Test LATS when agent is not available."""
        mock_get_agent.return_value = None

        answer, meta = await _generate_lats_answer("query", "ocr", "explanation")

        assert answer == ""
        assert meta == {}


class TestEvaluateAnswerQuality:
    """Test _evaluate_answer_quality function."""

    @pytest.mark.asyncio
    async def test_evaluate_empty_answer(self) -> None:
        """Test evaluation of empty answer."""
        score = await _evaluate_answer_quality("", "ocr", "explanation")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_too_short_answer(self) -> None:
        """Test evaluation of very short answer."""
        score = await _evaluate_answer_quality("짧음", "ocr", "explanation")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_good_length_answer(self) -> None:
        """Test evaluation of properly sized answer."""
        answer = "적절한 길이의 답변입니다. " * 10
        ocr_text = "OCR 내용"

        score = await _evaluate_answer_quality(answer, ocr_text, "explanation")

        assert score > 0.4  # Should get base score + length bonus

    @pytest.mark.asyncio
    async def test_evaluate_number_matching(self) -> None:
        """Test evaluation rewards number matching."""
        answer = "2023년 매출은 100억원입니다."
        ocr_text = "2023년 매출 100억원 달성"

        score = await _evaluate_answer_quality(answer, ocr_text, "explanation")

        assert score > 0.6  # Should get number matching bonus

    @pytest.mark.asyncio
    async def test_evaluate_no_numbers_in_ocr(self) -> None:
        """Test evaluation when OCR has no numbers."""
        answer = "일반적인 설명입니다. " * 5
        ocr_text = "숫자 없는 텍스트"

        score = await _evaluate_answer_quality(answer, ocr_text, "explanation")

        # Should get partial number_match_weight
        assert score >= 0.4

    @pytest.mark.asyncio
    async def test_evaluate_with_forbidden_patterns(self) -> None:
        """Test evaluation penalizes forbidden patterns."""
        answer = "- 불릿 리스트\n- 항목들\n" * 5
        ocr_text = "데이터"

        score = await _evaluate_answer_quality(answer, ocr_text, "explanation")

        # Should not get no_forbidden bonus
        assert score < 0.8

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_kg")
    async def test_evaluate_with_kg_constraints(self, mock_get_kg: Mock) -> None:
        """Test evaluation considers KG constraints when available."""
        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        from src.web.routers.workspace_generation import AnswerQualityWeights

        weights = AnswerQualityWeights(constraint_weight=0.2)

        answer = "적절한 답변입니다. " * 10
        ocr_text = "데이터"

        score = await _evaluate_answer_quality(answer, ocr_text, "explanation", weights)

        # Should attempt to apply constraint weight
        assert score > 0.4


class TestLATSEvaluateAnswerWithNode:
    """Test _lats_evaluate_answer with SearchNode."""

    @pytest.mark.asyncio
    async def test_lats_evaluate_empty_answer(self) -> None:
        """Test LATS evaluation with empty answer."""
        mock_node = MagicMock()
        mock_state = MagicMock()
        mock_state.current_answer = ""
        mock_state.ocr_text = "OCR"
        mock_node.state = mock_state

        score = await _lats_evaluate_answer(mock_node)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_lats_evaluate_good_answer(self) -> None:
        """Test LATS evaluation with good answer."""
        mock_node = MagicMock()
        mock_state = MagicMock()
        mock_state.current_answer = "좋은 답변입니다. " * 10
        mock_state.ocr_text = "OCR 내용"
        mock_state.metadata = {"query_type": "explanation"}
        mock_node.state = mock_state

        score = await _lats_evaluate_answer(mock_node)

        assert score > 0.4  # Should get base score + bonuses

    @pytest.mark.asyncio
    async def test_lats_evaluate_with_numbers(self) -> None:
        """Test LATS evaluation rewards number matching."""
        mock_node = MagicMock()
        mock_state = MagicMock()
        mock_state.current_answer = "2023년 매출 100억원"
        mock_state.ocr_text = "2023년 매출은 100억원입니다"
        mock_state.metadata = {"query_type": "table_summary"}
        mock_node.state = mock_state

        score = await _lats_evaluate_answer(mock_node)

        assert score > 0.6  # Should get number matching bonus

    @pytest.mark.asyncio
    @patch("src.web.routers.workspace_generation._get_kg")
    async def test_lats_evaluate_with_kg(self, mock_get_kg: Mock) -> None:
        """Test LATS evaluation with KG available."""
        mock_kg = MagicMock()
        mock_get_kg.return_value = mock_kg

        mock_node = MagicMock()
        mock_state = MagicMock()
        mock_state.current_answer = "적절한 답변입니다. " * 10
        mock_state.ocr_text = "OCR"
        mock_state.metadata = {"query_type": "explanation"}
        mock_node.state = mock_state

        score = await _lats_evaluate_answer(mock_node)

        # Should apply constraint weight
        assert score > 0.4
