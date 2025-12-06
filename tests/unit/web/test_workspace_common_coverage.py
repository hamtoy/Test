"""Comprehensive test coverage for src/web/routers/workspace_common.py."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.web.routers.workspace_common import (
    LATS_WEIGHTS_PRESETS,
    AnswerQualityWeights,
    _difficulty_hint,
    _evaluate_answer_quality,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator,
    _lats_evaluate_answer,
    set_dependencies,
)


class TestAnswerQualityWeights:
    """Test AnswerQualityWeights dataclass."""

    def test_default_weights(self) -> None:
        """Test default weight values."""
        weights = AnswerQualityWeights()

        assert weights.base_score == 0.4
        assert weights.length_weight == 0.10
        assert weights.number_match_weight == 0.25
        assert weights.no_forbidden_weight == 0.15
        assert weights.constraint_weight == 0.10

    def test_custom_weights(self) -> None:
        """Test custom weight values."""
        weights = AnswerQualityWeights(
            base_score=0.5,
            number_match_weight=0.35,
            min_length=20,
        )

        assert weights.base_score == 0.5
        assert weights.number_match_weight == 0.35
        assert weights.min_length == 20

    def test_weights_presets_exist(self) -> None:
        """Test all weight presets are defined."""
        expected_presets = [
            "explanation",
            "table_summary",
            "comparison",
            "trend_analysis",
            "strict",
        ]

        for preset in expected_presets:
            assert preset in LATS_WEIGHTS_PRESETS
            assert isinstance(LATS_WEIGHTS_PRESETS[preset], AnswerQualityWeights)


class TestDependencyInjection:
    """Test dependency injection functions."""

    def test_set_dependencies(self) -> None:
        """Test set_dependencies updates module globals."""
        from src.web.routers import workspace_common

        mock_config = MagicMock()
        mock_agent = MagicMock()
        mock_kg = MagicMock()
        mock_pipeline = MagicMock()

        set_dependencies(mock_config, mock_agent, mock_kg, mock_pipeline)

        assert workspace_common._config == mock_config
        assert workspace_common.agent == mock_agent
        assert workspace_common.kg == mock_kg
        assert workspace_common.pipeline == mock_pipeline

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_agent_from_registry(self, mock_get_registry: Mock) -> None:
        """Test _get_agent retrieves from registry."""
        mock_registry = MagicMock()
        mock_agent = MagicMock()
        mock_registry.agent = mock_agent
        mock_get_registry.return_value = mock_registry

        result = _get_agent()

        assert result == mock_agent

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_agent_registry_failure_fallback(self, mock_get_registry: Mock) -> None:
        """Test _get_agent falls back to api module on registry failure."""
        mock_get_registry.side_effect = RuntimeError("Registry not initialized")

        with patch("src.web.api.agent", MagicMock()):
            _get_agent()
            # Should attempt fallback

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_kg_from_registry(self, mock_get_registry: Mock) -> None:
        """Test _get_kg retrieves from registry."""
        mock_registry = MagicMock()
        mock_kg = MagicMock()
        mock_registry.kg = mock_kg
        mock_get_registry.return_value = mock_registry

        result = _get_kg()

        assert result == mock_kg

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_pipeline_from_registry(self, mock_get_registry: Mock) -> None:
        """Test _get_pipeline retrieves from registry."""
        mock_registry = MagicMock()
        mock_pipeline = MagicMock()
        mock_registry.pipeline = mock_pipeline
        mock_get_registry.return_value = mock_registry

        result = _get_pipeline()

        assert result == mock_pipeline

    @patch("src.web.routers.workspace_common.get_registry")
    @patch("src.web.routers.workspace_common.AppConfig")
    def test_get_config_from_registry(
        self, mock_app_config: Mock, mock_get_registry: Mock
    ) -> None:
        """Test _get_config retrieves from registry."""
        mock_registry = MagicMock()
        mock_config = MagicMock()
        mock_config.workspace_timeout = 120
        mock_config.workspace_unified_timeout = 180
        mock_config.qa_single_timeout = 60
        mock_config.qa_batch_timeout = 300
        mock_registry.config = mock_config
        mock_get_registry.return_value = mock_registry

        result = _get_config()

        assert result == mock_config

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_config_validates_timeouts(self, mock_get_registry: Mock) -> None:
        """Test _get_config validates timeout fields are integers."""
        mock_registry = MagicMock()
        mock_config = MagicMock()
        # Simulate MagicMock timeout (not an int)
        mock_config.workspace_timeout = MagicMock()
        mock_registry.config = mock_config
        mock_get_registry.return_value = mock_registry

        result = _get_config()

        # Should have set default timeout values
        assert isinstance(result.workspace_timeout, int)

    @patch("src.web.routers.workspace_common.get_registry")
    @patch("src.web.routers.workspace_common.CrossValidationSystem")
    def test_get_validator_creates_new(
        self, mock_cv_cls: Mock, mock_get_registry: Mock
    ) -> None:
        """Test _get_validator creates new validator when not cached."""
        mock_registry = MagicMock()
        mock_registry.validator = None
        mock_kg = MagicMock()
        mock_registry.kg = mock_kg
        mock_get_registry.return_value = mock_registry

        mock_validator = MagicMock()
        mock_cv_cls.return_value = mock_validator

        result = _get_validator()

        assert result == mock_validator
        mock_cv_cls.assert_called_once_with(mock_kg)
        mock_registry.register_validator.assert_called_once_with(mock_validator)

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_validator_returns_cached(self, mock_get_registry: Mock) -> None:
        """Test _get_validator returns cached validator."""
        mock_registry = MagicMock()
        mock_validator = MagicMock()
        mock_registry.validator = mock_validator
        mock_get_registry.return_value = mock_registry

        result = _get_validator()

        assert result == mock_validator

    @patch("src.web.routers.workspace_common.get_registry")
    def test_get_validator_no_kg(self, mock_get_registry: Mock) -> None:
        """Test _get_validator returns None when kg is None."""
        mock_registry = MagicMock()
        mock_registry.validator = None
        mock_registry.kg = None
        mock_get_registry.return_value = mock_registry

        result = _get_validator()

        assert result is None


class TestDifficultyHint:
    """Test difficulty hint generation."""

    def test_difficulty_hint_short_text(self) -> None:
        """Test difficulty hint for short text."""
        short_text = "a" * 1000

        result = _difficulty_hint(short_text)

        assert result == "불필요한 서론 없이 핵심을 짧게 서술하세요."

    def test_difficulty_hint_medium_text(self) -> None:
        """Test difficulty hint for medium text."""
        medium_text = "a" * 2500

        result = _difficulty_hint(medium_text)

        assert result == "본문이 길어 핵심 숫자·근거만 간결히 답하세요."

    def test_difficulty_hint_long_text(self) -> None:
        """Test difficulty hint for long text."""
        long_text = "a" * 5000

        result = _difficulty_hint(long_text)

        assert result == "본문이 길어 핵심 숫자·근거만 간결히 답하세요."


class TestAnswerQualityEvaluation:
    """Test answer quality evaluation function."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_perfect_score(self) -> None:
        """Test evaluation with perfect answer."""
        answer = "정확한 답변입니다. 기준에 따라 2023년 매출은 100억원입니다."
        query = "매출이 얼마인가요?"
        ocr_text = "2023년 매출: 100억원, 2022년: 90억원"
        rules_list = ["숫자 포함", "근거 제시"]
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        assert 0.8 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_too_short(self) -> None:
        """Test evaluation penalizes too short answers."""
        answer = "짧음"
        query = "상세 설명"
        ocr_text = "긴 텍스트 내용..."
        rules_list = []
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        assert score < 0.6  # Should be penalized for short length

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_too_long(self) -> None:
        """Test evaluation penalizes too long answers."""
        answer = "가" * 1500
        query = "간단히 설명"
        ocr_text = "데이터"
        rules_list = []
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        assert score < 0.7  # Should be penalized for excessive length

    @pytest.mark.asyncio
    @patch("checks.detect_forbidden_patterns.find_violations")
    async def test_evaluate_answer_quality_with_violations(
        self, mock_find_violations: Mock
    ) -> None:
        """Test evaluation penalizes forbidden patterns."""
        answer = "- 불릿 리스트 답변"
        query = "설명"
        ocr_text = "내용"
        rules_list = []
        weights = AnswerQualityWeights()
        mock_find_violations.return_value = [{"type": "bullet"}]

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        # Should not get no_forbidden_weight bonus
        assert score < weights.base_score + weights.no_forbidden_weight + 0.2

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_number_matching(self) -> None:
        """Test evaluation rewards number matching."""
        answer = "2023년 매출은 100억원, 2022년은 90억원"
        query = "매출 추이"
        ocr_text = "2023년 100억원 2022년 90억원"
        rules_list = []
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        # Should get number_match_weight bonus
        assert score >= weights.base_score + weights.number_match_weight * 0.5

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_no_numbers_in_ocr(self) -> None:
        """Test evaluation when OCR has no numbers."""
        answer = "일반적인 설명 답변입니다"
        query = "설명"
        ocr_text = "숫자가 없는 텍스트"
        rules_list = []
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(
            answer, query, ocr_text, rules_list, weights
        )

        # Should still get reasonable score without number penalty
        assert score >= weights.base_score


class TestLATSEvaluateAnswer:
    """Test LATS answer evaluation."""

    @pytest.mark.asyncio
    async def test_lats_evaluate_answer_placeholder(self) -> None:
        """Test _lats_evaluate_answer returns placeholder value."""
        mock_node = MagicMock()

        score = await _lats_evaluate_answer(mock_node)

        assert score == 0.5  # Placeholder implementation
