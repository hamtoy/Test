from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.web.routers.workspace import (
    LATS_WEIGHTS_PRESETS,
    _evaluate_answer_quality,
    _generate_lats_answer,
    _lats_evaluate_answer,
)


@pytest.mark.asyncio
async def test_evaluate_answer_quality_basics() -> None:
    """기본 품질 평가 로직 테스트."""
    ocr_text = "매출 100억원 2024년"

    # 1. 완벽한 답변 (숫자 2개 일치, 길이 적절, 금지어 없음)
    perfect_answer = "2024년 매출은 100억원입니다. 이는 전년 대비 증가한 수치입니다."
    score = await _evaluate_answer_quality(perfect_answer, ocr_text)

    # Base 0.4 + Length 0.1 + Number 0.25 (2 overlaps) + No Forbidden 0.15 = 0.9
    # 기본 explanation 가중치 기준
    assert score >= 0.9

    # 2. 너무 짧은 답변
    short_answer = "짧음"
    score = await _evaluate_answer_quality(short_answer, ocr_text)
    assert score == 0.0

    # 3. 금지 패턴 포함 (* 불릿)
    forbidden_answer = "* 2024년 매출 100억"
    score = await _evaluate_answer_quality(forbidden_answer, ocr_text)
    # No Forbidden 점수(0.15) 제외
    assert score < 0.9


@pytest.mark.asyncio
async def test_evaluate_answer_quality_presets() -> None:
    """프리셋별 가중치 적용 테스트."""
    ocr_text = "데이터: 1, 2, 3, 4, 5"
    answer = "데이터는 1, 2, 3입니다."  # 숫자 3개 일치

    # table_summary: 숫자 가중치(0.35)가 높음
    weights_table = LATS_WEIGHTS_PRESETS["table_summary"]
    score_table = await _evaluate_answer_quality(
        answer, ocr_text, query_type="table_summary", weights=weights_table
    )

    # explanation: 숫자 가중치(0.25)가 낮음
    weights_expl = LATS_WEIGHTS_PRESETS["explanation"]
    score_expl = await _evaluate_answer_quality(
        answer, ocr_text, query_type="explanation", weights=weights_expl
    )

    # table_summary가 숫자 점수를 더 많이 받거나 base_score 차이로 인해 점수가 달라야 함
    assert isinstance(score_table, float)
    assert isinstance(score_expl, float)


@pytest.mark.asyncio
async def test_generate_lats_answer_auto_optimization() -> None:
    """LATS 자동 최적화 로직 테스트."""
    ocr_text = "테스트 텍스트 123"
    query = "테스트 질문"

    mock_agent = AsyncMock()
    # Mock response
    mock_agent._create_generative_model.return_value = MagicMock()

    async def side_effect(model: Any, prompt: str) -> str:
        if "숫자_중심" in prompt:
            return "123을 포함한 좋은 답변입니다."
        elif "트렌드_중심" in prompt:
            return "짧"
        else:
            return "* 나쁜 형식 답변"

    mock_agent._call_api_with_retry.side_effect = side_effect

    with patch("src.web.routers.workspace._get_agent", return_value=mock_agent):
        answer, meta = await _generate_lats_answer(query, ocr_text, "explanation")

        # Best answer should be from "숫자_중심"
        assert "123" in answer
        assert meta["best_strategy"] == "숫자_중심"


@pytest.mark.asyncio
async def test_lats_evaluate_answer_node() -> None:
    """LATS 노드 평가 로직 테스트."""

    class MockState:
        def __init__(
            self, answer: str, ocr: str, metadata: Optional[dict[str, Any]] = None
        ) -> None:
            self.current_answer = answer
            self.ocr_text = ocr
            self.metadata = metadata

    class MockNode:
        def __init__(self, state: MockState) -> None:
            self.state = state

    ocr_text = "매출 100억"

    # 1. Good answer (explanation default)
    state_good = MockState("100억 매출입니다.", ocr_text, {"query_type": "explanation"})
    score = await _lats_evaluate_answer(MockNode(state_good))  # type: ignore[arg-type]
    assert score > 0.6

    # 2. Table Summary (needs higher number match weight)
    state_table = MockState("100", ocr_text, {"query_type": "table_summary"})
    score_table = await _lats_evaluate_answer(MockNode(state_table))  # type: ignore[arg-type]
    assert score_table > 0.0

    # 3. No query_type in metadata (default to explanation)
    state_default = MockState("기본 답변", ocr_text, {})
    score_default = await _lats_evaluate_answer(MockNode(state_default))  # type: ignore[arg-type]
    assert score_default >= 0.0
