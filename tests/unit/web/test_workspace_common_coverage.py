"""Comprehensive tests for src/web/routers/workspace_common.py to improve coverage to 80%+."""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig
from src.web.routers.workspace_common import (
    LATS_WEIGHTS_PRESETS,
    MAX_REWRITE_ATTEMPTS,
    AnswerQualityWeights,
    DEFAULT_LATS_WEIGHTS,
    _difficulty_hint,
    _evaluate_answer_quality,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator,
    set_dependencies,
)


@pytest.fixture
def mock_agent():
    """Mock GeminiAgent."""
    agent = AsyncMock()
    agent.rewrite_best_answer = AsyncMock(return_value="Rewritten answer")
    return agent


@pytest.fixture
def mock_kg():
    """Mock QAKnowledgeGraph."""
    kg = MagicMock()
    kg.get_rules_for_query_type = MagicMock(return_value=[])
    return kg


@pytest.fixture
def mock_pipeline():
    """Mock IntegratedQAPipeline."""
    pipeline = AsyncMock()
    return pipeline


@pytest.fixture
def mock_config():
    """Mock AppConfig."""
    config = MagicMock(spec=AppConfig)
    config.workspace_timeout = 30
    config.workspace_unified_timeout = 45
    config.qa_single_timeout = 20
    config.qa_batch_timeout = 120
    config.gemini_api_key = "AIza" + "0" * 35
    return config


class TestAnswerQualityWeights:
    """Test AnswerQualityWeights dataclass."""

    def test_default_weights(self):
        """Test default weight values."""
        weights = AnswerQualityWeights()
        assert weights.base_score == 0.4
        assert weights.length_weight == 0.10
        assert weights.number_match_weight == 0.25
        assert weights.no_forbidden_weight == 0.15
        assert weights.constraint_weight == 0.10
        assert weights.min_length == 15
        assert weights.max_length == 1200
        assert weights.min_number_overlap == 1

    def test_custom_weights(self):
        """Test creating custom weights."""
        weights = AnswerQualityWeights(
            base_score=0.5,
            length_weight=0.2,
            number_match_weight=0.3,
            min_length=20,
            max_length=1000,
        )
        assert weights.base_score == 0.5
        assert weights.length_weight == 0.2
        assert weights.number_match_weight == 0.3
        assert weights.min_length == 20
        assert weights.max_length == 1000

    def test_weights_are_frozen(self):
        """Test that AnswerQualityWeights instances are immutable."""
        weights = AnswerQualityWeights()
        with pytest.raises(AttributeError):
            weights.base_score = 0.9  # type: ignore


class TestLatsWeightsPresets:
    """Test LATS_WEIGHTS_PRESETS configuration."""

    def test_presets_exist(self):
        """Test that expected presets exist."""
        assert "explanation" in LATS_WEIGHTS_PRESETS
        assert "table_summary" in LATS_WEIGHTS_PRESETS
        assert "comparison" in LATS_WEIGHTS_PRESETS
        assert "trend_analysis" in LATS_WEIGHTS_PRESETS
        assert "strict" in LATS_WEIGHTS_PRESETS

    def test_explanation_preset(self):
        """Test explanation preset values."""
        weights = LATS_WEIGHTS_PRESETS["explanation"]
        assert weights.number_match_weight == 0.25
        assert weights.length_weight == 0.15

    def test_table_summary_preset(self):
        """Test table_summary preset prioritizes numbers."""
        weights = LATS_WEIGHTS_PRESETS["table_summary"]
        assert weights.number_match_weight == 0.35  # Higher for tables
        assert weights.base_score == 0.35

    def test_strict_preset(self):
        """Test strict preset enforces formatting."""
        weights = LATS_WEIGHTS_PRESETS["strict"]
        assert weights.no_forbidden_weight == 0.25  # Highest
        assert weights.base_score == 0.30

    def test_default_lats_weights(self):
        """Test DEFAULT_LATS_WEIGHTS points to explanation."""
        assert DEFAULT_LATS_WEIGHTS == LATS_WEIGHTS_PRESETS["explanation"]


class TestSetDependencies:
    """Test set_dependencies function."""

    def test_set_dependencies_registers_all(self, mock_config, mock_agent, mock_kg, mock_pipeline):
        """Test set_dependencies registers all dependencies."""
        import src.web.routers.workspace_common as wc

        set_dependencies(mock_config, mock_agent, mock_kg, mock_pipeline)

        assert wc._config == mock_config
        assert wc.agent == mock_agent
        assert wc.kg == mock_kg
        assert wc.pipeline == mock_pipeline

    def test_set_dependencies_resets_validator(self, mock_config, mock_agent, mock_kg):
        """Test set_dependencies resets validator in registry."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry_getter.return_value = mock_registry

            set_dependencies(mock_config, mock_agent, mock_kg, None)

            mock_registry.register_validator.assert_called_once_with(None)


class TestGetAgent:
    """Test _get_agent function."""

    def test_get_agent_from_registry(self, mock_agent):
        """Test _get_agent retrieves from registry."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.agent = mock_agent
            mock_registry_getter.return_value = mock_registry

            agent = _get_agent()

            assert agent == mock_agent

    def test_get_agent_fallback_to_api_module(self, mock_agent):
        """Test _get_agent falls back to api module when registry fails."""
        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api") as mock_api:
                mock_api.agent = mock_agent

                agent = _get_agent()

                assert agent == mock_agent

    def test_get_agent_fallback_to_module_global(self, mock_agent):
        """Test _get_agent uses module global as last resort."""
        import src.web.routers.workspace_common as wc

        wc.agent = mock_agent

        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api", spec=[]):  # No agent attribute

                agent = _get_agent()

                assert agent == mock_agent

    def test_get_agent_returns_none_when_unavailable(self):
        """Test _get_agent returns None when agent unavailable."""
        import src.web.routers.workspace_common as wc

        wc.agent = None

        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api", spec=[]):

                agent = _get_agent()

                assert agent is None


class TestGetKg:
    """Test _get_kg function."""

    def test_get_kg_from_registry(self, mock_kg):
        """Test _get_kg retrieves from registry."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.kg = mock_kg
            mock_registry_getter.return_value = mock_registry

            kg = _get_kg()

            assert kg == mock_kg

    def test_get_kg_fallback_to_api_module(self, mock_kg):
        """Test _get_kg falls back to api module."""
        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api") as mock_api:
                mock_api.kg = mock_kg

                kg = _get_kg()

                assert kg == mock_kg

    def test_get_kg_returns_none_when_unavailable(self):
        """Test _get_kg returns None when KG unavailable."""
        import src.web.routers.workspace_common as wc

        wc.kg = None

        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api", spec=[]):

                kg = _get_kg()

                assert kg is None


class TestGetPipeline:
    """Test _get_pipeline function."""

    def test_get_pipeline_from_registry(self, mock_pipeline):
        """Test _get_pipeline retrieves from registry."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.pipeline = mock_pipeline
            mock_registry_getter.return_value = mock_registry

            pipeline = _get_pipeline()

            assert pipeline == mock_pipeline

    def test_get_pipeline_fallback_to_api_module(self, mock_pipeline):
        """Test _get_pipeline falls back to api module."""
        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api") as mock_api:
                mock_api.pipeline = mock_pipeline

                pipeline = _get_pipeline()

                assert pipeline == mock_pipeline


class TestGetConfig:
    """Test _get_config function."""

    def test_get_config_from_registry(self, mock_config):
        """Test _get_config retrieves from registry."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.config = mock_config
            mock_registry_getter.return_value = mock_registry

            config = _get_config()

            assert config == mock_config

    def test_get_config_fallback_to_api_module(self, mock_config):
        """Test _get_config falls back to api module."""
        with patch("src.web.routers/workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api") as mock_api:
                mock_api.config = mock_config

                config = _get_config()

                assert config == mock_config

    def test_get_config_creates_default_when_unavailable(self):
        """Test _get_config creates default AppConfig when unavailable."""
        import src.web.routers.workspace_common as wc

        wc._config = None

        with patch("src.web.routers.workspace_common.get_registry", side_effect=RuntimeError):
            with patch("src.web.api", spec=[]):

                config = _get_config()

                assert isinstance(config, AppConfig)

    def test_get_config_fixes_invalid_timeouts(self):
        """Test _get_config fixes invalid timeout values."""
        mock_bad_config = MagicMock(spec=AppConfig)
        mock_bad_config.workspace_timeout = MagicMock()  # Not an int
        mock_bad_config.workspace_unified_timeout = "not_int"  # Wrong type
        mock_bad_config.qa_single_timeout = None
        mock_bad_config.qa_batch_timeout = []

        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.config = mock_bad_config
            mock_registry_getter.return_value = mock_registry

            config = _get_config()

            # Should have fixed timeout values
            assert isinstance(config.workspace_timeout, int)
            assert isinstance(config.workspace_unified_timeout, int)
            assert isinstance(config.qa_single_timeout, int)
            assert isinstance(config.qa_batch_timeout, int)


class TestGetValidator:
    """Test _get_validator function."""

    def test_get_validator_from_registry_cache(self):
        """Test _get_validator returns cached validator from registry."""
        mock_validator = MagicMock()

        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.validator = mock_validator
            mock_registry_getter.return_value = mock_registry

            validator = _get_validator()

            assert validator == mock_validator

    def test_get_validator_creates_new_when_missing(self, mock_kg):
        """Test _get_validator creates new validator when not cached."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.validator = None
            mock_registry.kg = mock_kg
            mock_registry_getter.return_value = mock_registry

            with patch("src.web.routers.workspace_common.CrossValidationSystem") as mock_cv:
                mock_validator = MagicMock()
                mock_cv.return_value = mock_validator

                validator = _get_validator()

                assert validator == mock_validator
                mock_registry.register_validator.assert_called_once_with(mock_validator)

    def test_get_validator_returns_none_without_kg(self):
        """Test _get_validator returns None when KG unavailable."""
        with patch("src.web.routers.workspace_common.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.validator = None
            mock_registry.kg = None
            mock_registry_getter.return_value = mock_registry

            validator = _get_validator()

            assert validator is None

    def test_get_validator_handles_exceptions(self):
        """Test _get_validator handles exceptions gracefully."""
        with patch("src.web.routers.workspace_common.get_registry", side_effect=Exception("Error")):

            validator = _get_validator()

            assert validator is None


class TestDifficultyHint:
    """Test _difficulty_hint function."""

    def test_difficulty_hint_long_text(self):
        """Test difficulty hint for very long text."""
        long_text = "a" * 5000

        hint = _difficulty_hint(long_text)

        assert "길어" in hint or "핵심" in hint

    def test_difficulty_hint_medium_text(self):
        """Test difficulty hint for medium length text."""
        medium_text = "a" * 3000

        hint = _difficulty_hint(medium_text)

        assert "짧게" in hint or "간결히" in hint or "핵심" in hint

    def test_difficulty_hint_short_text(self):
        """Test difficulty hint for short text."""
        short_text = "a" * 1000

        hint = _difficulty_hint(short_text)

        # Should return medium hint
        assert len(hint) > 0


class TestEvaluateAnswerQuality:
    """Test _evaluate_answer_quality function."""

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_perfect_answer(self):
        """Test evaluation of high-quality answer."""
        answer = "2023년 매출은 100억원, 2024년은 150억원으로 50% 증가했습니다."
        query = "매출 증가율은?"
        ocr_text = "2023년 매출: 100억원, 2024년 매출: 150억원"
        rules_list = ["기준을 명확히 제시하세요"]
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should score high
        assert score > 0.7

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_good_length(self):
        """Test length evaluation."""
        answer = "This is a reasonably long answer that meets the minimum length requirement."
        query = "Test query"
        ocr_text = "Test OCR text"
        rules_list = []
        weights = AnswerQualityWeights(min_length=10, max_length=200)

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should include length_weight
        assert score >= weights.base_score + weights.length_weight

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_too_short(self):
        """Test penalty for too short answer."""
        answer = "Short"
        query = "Test"
        ocr_text = "Text"
        rules_list = []
        weights = AnswerQualityWeights(min_length=50)

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should not get length bonus
        assert score == weights.base_score + weights.no_forbidden_weight  # Only base + no forbidden

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_number_matching(self):
        """Test number matching evaluation."""
        answer = "The value is 42 and 100."
        query = "What are the values?"
        ocr_text = "Values: 42, 100, 200"
        rules_list = []
        weights = AnswerQualityWeights(min_number_overlap=1)

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should get partial number match weight (2 out of 3 numbers)
        assert score > weights.base_score

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_forbidden_patterns(self):
        """Test detection of forbidden patterns."""
        answer = "Answer with **bold** and - bullet points"
        query = "Test"
        ocr_text = "Test"
        rules_list = []
        weights = AnswerQualityWeights()

        with patch("src.web.routers.workspace_common.find_violations", return_value=[{"type": "markdown"}]):
            score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

            # Should not get no_forbidden_weight
            assert score == weights.base_score + weights.length_weight  # No forbidden weight

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_rule_keywords(self):
        """Test rule keyword matching."""
        answer = "정확한 근거에 기준하여 답변드립니다."
        query = "Test"
        ocr_text = "Test"
        rules_list = ["기준을 명시하세요", "근거를 제시하세요"]
        weights = AnswerQualityWeights()

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should get constraint_weight for matching keywords
        assert score >= weights.base_score + weights.constraint_weight

    @pytest.mark.asyncio
    async def test_evaluate_answer_quality_caps_at_1(self):
        """Test score is capped at 1.0."""
        answer = "Perfect answer with 100 and 200 and precise information with exact references."
        query = "Test"
        ocr_text = "100 200"
        rules_list = ["기준", "근거"]
        weights = AnswerQualityWeights(
            base_score=0.9,
            length_weight=0.5,
            number_match_weight=0.5,
        )

        score = await _evaluate_answer_quality(answer, query, ocr_text, rules_list, weights)

        # Should be capped at 1.0
        assert score <= 1.0


class TestConstants:
    """Test module constants."""

    def test_max_rewrite_attempts(self):
        """Test MAX_REWRITE_ATTEMPTS is defined."""
        assert MAX_REWRITE_ATTEMPTS == 3

    def test_difficulty_levels_defined(self):
        """Test difficulty level messages are defined."""
        import src.web.routers.workspace_common as wc

        assert hasattr(wc, "_difficulty_levels")
        assert "long" in wc._difficulty_levels
        assert "medium" in wc._difficulty_levels
