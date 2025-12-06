"""Tests for qa_common module helper functions and caching."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


from src.config import AppConfig
from src.web.routers.qa_common import (
    _CachedKG,
    _difficulty_hint,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator_class,
    get_cached_kg,
    set_dependencies,
)


class TestCachedKG:
    """Tests for _CachedKG wrapper class."""

    def test_get_formatting_rules_caches_result(self) -> None:
        """Test that get_formatting_rules caches results."""
        mock_kg = MagicMock()
        mock_kg.get_formatting_rules = MagicMock(return_value="Formatting rules text")

        cached_kg = _CachedKG(mock_kg)

        # First call - should call base
        result1 = cached_kg.get_formatting_rules("template_type1")
        assert result1 == "Formatting rules text"
        assert mock_kg.get_formatting_rules.call_count == 1

        # Second call with same type - should return cached
        result2 = cached_kg.get_formatting_rules("template_type1")
        assert result2 == "Formatting rules text"
        assert mock_kg.get_formatting_rules.call_count == 1  # No additional call

    def test_get_formatting_rules_different_types(self) -> None:
        """Test that different template types are cached separately."""
        mock_kg = MagicMock()
        mock_kg.get_formatting_rules = MagicMock(side_effect=lambda t: f"Rules for {t}")

        cached_kg = _CachedKG(mock_kg)

        result1 = cached_kg.get_formatting_rules("type1")
        result2 = cached_kg.get_formatting_rules("type2")

        assert result1 == "Rules for type1"
        assert result2 == "Rules for type2"
        assert mock_kg.get_formatting_rules.call_count == 2

    def test_find_relevant_rules_caches_result(self) -> None:
        """Test that find_relevant_rules caches results."""
        mock_kg = MagicMock()
        mock_kg.find_relevant_rules = MagicMock(
            return_value=["rule1", "rule2", "rule3"]
        )

        cached_kg = _CachedKG(mock_kg)

        # First call
        result1 = cached_kg.find_relevant_rules("test query", k=10)
        assert result1 == ["rule1", "rule2", "rule3"]
        assert mock_kg.find_relevant_rules.call_count == 1

        # Second call with same query and k - should return cached
        result2 = cached_kg.find_relevant_rules("test query", k=10)
        assert result2 == ["rule1", "rule2", "rule3"]
        assert mock_kg.find_relevant_rules.call_count == 1  # No additional call

    def test_find_relevant_rules_different_k_values(self) -> None:
        """Test that different k values create different cache keys."""
        mock_kg = MagicMock()
        mock_kg.find_relevant_rules = MagicMock(
            side_effect=lambda q, k: [f"rule_{i}" for i in range(k)]
        )

        cached_kg = _CachedKG(mock_kg)

        result1 = cached_kg.find_relevant_rules("test query", k=5)
        result2 = cached_kg.find_relevant_rules("test query", k=10)

        assert len(result1) == 5
        assert len(result2) == 10
        assert mock_kg.find_relevant_rules.call_count == 2

    def test_find_relevant_rules_truncates_long_query(self) -> None:
        """Test that long queries are truncated for caching."""
        mock_kg = MagicMock()
        mock_kg.find_relevant_rules = MagicMock(return_value=["rule1"])

        cached_kg = _CachedKG(mock_kg)

        # Create a query longer than 500 chars
        long_query = "a" * 600
        result = cached_kg.find_relevant_rules(long_query, k=10)

        assert result == ["rule1"]
        # Check that cache key uses truncated query (first 500 chars)
        assert (long_query[:500], 10) in cached_kg._rules

    def test_get_constraints_for_query_type_handles_invalid_string(self) -> None:
        """Test that get_constraints_for_query_type handles string return gracefully."""
        mock_kg = MagicMock()
        # Simulate invalid return type (string instead of list)
        mock_kg.get_constraints_for_query_type = MagicMock(
            return_value="no constraints"
        )

        cached_kg = _CachedKG(mock_kg)

        # Should return empty list instead of crashing
        result = cached_kg.get_constraints_for_query_type("test_type")
        assert result == []
        assert mock_kg.get_constraints_for_query_type.call_count == 1

    def test_get_constraints_for_query_type_handles_valid_list(self) -> None:
        """Test that get_constraints_for_query_type handles valid list return."""
        mock_kg = MagicMock()
        valid_constraints = [{"category": "query", "description": "test constraint"}]
        mock_kg.get_constraints_for_query_type = MagicMock(
            return_value=valid_constraints
        )

        cached_kg = _CachedKG(mock_kg)

        result = cached_kg.get_constraints_for_query_type("test_type")
        assert result == valid_constraints
        assert mock_kg.get_constraints_for_query_type.call_count == 1

    def test_get_formatting_rules_for_query_type_handles_invalid_string(self) -> None:
        """Test that get_formatting_rules_for_query_type handles string return gracefully."""
        mock_kg = MagicMock()
        # Simulate invalid return type (string instead of list)
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value="no rules")

        cached_kg = _CachedKG(mock_kg)

        # Should return empty list instead of crashing
        result = cached_kg.get_formatting_rules_for_query_type("test_type")
        assert result == []
        assert mock_kg.get_formatting_rules_for_query_type.call_count == 1

    def test_get_formatting_rules_for_query_type_handles_valid_list(self) -> None:
        """Test that get_formatting_rules_for_query_type handles valid list return."""
        mock_kg = MagicMock()
        valid_rules = [{"description": "test rule"}]
        mock_kg.get_formatting_rules_for_query_type = MagicMock(
            return_value=valid_rules
        )

        cached_kg = _CachedKG(mock_kg)

        result = cached_kg.get_formatting_rules_for_query_type("test_type")
        assert result == valid_rules
        assert mock_kg.get_formatting_rules_for_query_type.call_count == 1


class TestGetterFunctions:
    """Tests for dependency getter functions."""

    def test_get_agent_from_api_module(self) -> None:
        """Test _get_agent retrieves agent from api module."""
        mock_agent = MagicMock()
        with patch("src.web.api.agent", mock_agent):
            result = _get_agent()
            assert result is mock_agent

    def test_get_agent_exception_fallback(self) -> None:
        """Test _get_agent falls back when api module raises exception."""
        with (
            patch("src.web.routers.qa_common.agent", None),
            patch("src.web.api.agent", None),
        ):
            result = _get_agent()
            assert result is None

    def test_get_pipeline_from_api_module(self) -> None:
        """Test _get_pipeline retrieves pipeline from api module."""
        mock_pipeline = MagicMock()
        with patch("src.web.api.pipeline", mock_pipeline):
            result = _get_pipeline()
            assert result is mock_pipeline

    def test_get_pipeline_exception_fallback(self) -> None:
        """Test _get_pipeline falls back when exception occurs."""
        with (
            patch("src.web.routers.qa_common.pipeline", None),
            patch("src.web.api.pipeline", None),
        ):
            result = _get_pipeline()
            assert result is None

    def test_get_kg_from_api_module(self) -> None:
        """Test _get_kg retrieves kg from api module."""
        mock_kg = MagicMock()
        with patch("src.web.api.kg", mock_kg):
            result = _get_kg()
            assert result is mock_kg

    def test_get_kg_exception_fallback(self) -> None:
        """Test _get_kg falls back when exception occurs."""
        with (
            patch("src.web.routers.qa_common.kg", None),
            patch("src.web.api.kg", None),
        ):
            result = _get_kg()
            assert result is None

    def test_get_config_sanitizes_timeout_values(self) -> None:
        """Test _get_config ensures timeout values are numeric."""
        mock_config = MagicMock(spec=AppConfig)
        # Set up mock attributes that might be MagicMock
        mock_config.qa_single_timeout = MagicMock()
        mock_config.qa_batch_timeout = 300
        mock_config.workspace_timeout = "invalid"
        mock_config.workspace_unified_timeout = 600

        with patch("src.web.api.config", mock_config):
            result = _get_config()

            # Should convert/fallback to defaults for invalid values
            assert isinstance(result.qa_single_timeout, int)
            assert isinstance(result.qa_batch_timeout, int)
            assert isinstance(result.workspace_timeout, int)
            assert isinstance(result.workspace_unified_timeout, int)

    def test_get_config_sanitizes_boolean_flags(self) -> None:
        """Test _get_config ensures boolean flags are properly set."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.enable_standard_response = MagicMock()
        mock_config.enable_lats = "invalid"

        with patch("src.web.api.config", mock_config):
            result = _get_config()

            # Should convert to booleans or fallback to False
            assert isinstance(result.enable_standard_response, bool)
            assert isinstance(result.enable_lats, bool)

    def test_get_config_exception_uses_fallback_config(self) -> None:
        """Test _get_config creates new AppConfig when all sources fail."""
        with (
            patch("src.web.routers.qa_common._config", None),
            patch("src.web.api.config", None),
            patch(
                "src.web.dependencies.get_config",
                side_effect=Exception("Dependencies failed"),
            ),
        ):
            result = _get_config()
            assert isinstance(result, AppConfig)

    def test_get_config_uses_module_level_config(self) -> None:
        """Test _get_config uses module-level _config when api module fails."""
        mock_config = AppConfig()
        with (
            patch("src.web.routers.qa_common._config", mock_config),
            patch("src.web.api.config", None),
        ):
            result = _get_config()
            assert result is mock_config

    def test_get_config_uses_dependencies_fallback(self) -> None:
        """Test _get_config falls back to dependencies.get_config."""
        mock_config = AppConfig()
        with (
            patch("src.web.routers.qa_common._config", None),
            patch("src.web.api.config", None),
            patch("src.web.dependencies.get_config", return_value=mock_config),
        ):
            result = _get_config()
            assert result is mock_config

    def test_get_validator_class_from_api_module(self) -> None:
        """Test _get_validator_class retrieves from api module."""

        mock_validator = MagicMock()
        with patch("src.web.api.CrossValidationSystem", mock_validator):
            result = _get_validator_class()
            assert result is mock_validator

    def test_get_validator_class_exception_fallback(self) -> None:
        """Test _get_validator_class falls back to default when import fails."""
        from src.analysis.cross_validation import CrossValidationSystem

        # Mock the api module import to fail
        import sys

        original_modules = sys.modules.copy()
        try:
            # Remove src.web.api from modules if it exists
            if "src.web.api" in sys.modules:
                del sys.modules["src.web.api"]

            # Mock import to fail
            with patch.dict("sys.modules", {"src.web.api": None}):
                result = _get_validator_class()
                assert result is CrossValidationSystem
        finally:
            # Restore original modules
            sys.modules.update(original_modules)


class TestDifficultyHint:
    """Tests for _difficulty_hint function."""

    def test_short_text_hint(self) -> None:
        """Test difficulty hint for short text."""
        short_text = "a" * 1000
        hint = _difficulty_hint(short_text)
        assert "필요 이상의 부연 없이" in hint
        assert "핵심 숫자" in hint

    def test_medium_text_hint(self) -> None:
        """Test difficulty hint for medium-length text."""
        medium_text = "a" * 2500
        hint = _difficulty_hint(medium_text)
        assert "본문이 길어" in hint
        assert "핵심만 압축" in hint

    def test_long_text_hint(self) -> None:
        """Test difficulty hint for long text."""
        long_text = "a" * 5000
        hint = _difficulty_hint(long_text)
        assert "본문이 매우 길어요" in hint
        assert "2-3문장 이내" in hint


class TestGetCachedKG:
    """Tests for get_cached_kg function."""

    def test_get_cached_kg_returns_none_when_no_kg(self) -> None:
        """Test that get_cached_kg returns None when no KG is available."""
        with patch("src.web.routers.qa_common._get_kg", return_value=None):
            result = get_cached_kg()
            assert result is None

    def test_get_cached_kg_creates_new_cache(self) -> None:
        """Test that get_cached_kg creates a new cached wrapper."""
        mock_kg = MagicMock()
        with patch("src.web.routers.qa_common._get_kg", return_value=mock_kg):
            # Clear any existing cache
            import src.web.routers.qa_common as qa_common_module

            qa_common_module._kg_cache = None
            qa_common_module._kg_cache_timestamp = None

            result = get_cached_kg()

            assert result is not None
            assert isinstance(result, _CachedKG)
            assert result._base is mock_kg

    def test_get_cached_kg_reuses_valid_cache(self) -> None:
        """Test that get_cached_kg reuses cache within TTL."""
        mock_kg = MagicMock()

        with patch("src.web.routers.qa_common._get_kg", return_value=mock_kg):
            # Clear cache first
            import src.web.routers.qa_common as qa_common_module

            qa_common_module._kg_cache = None
            qa_common_module._kg_cache_timestamp = None

            # First call creates cache
            result1 = get_cached_kg()

            # Second call reuses cache
            result2 = get_cached_kg()

            # Should return the same cached instance
            assert result1 is result2

    def test_get_cached_kg_expires_old_cache(self) -> None:
        """Test that get_cached_kg creates new cache after TTL."""
        mock_kg = MagicMock()

        with patch("src.web.routers.qa_common._get_kg", return_value=mock_kg):
            import src.web.routers.qa_common as qa_common_module

            # Set up expired cache
            old_cache = _CachedKG(mock_kg)
            qa_common_module._kg_cache = old_cache
            qa_common_module._kg_cache_timestamp = datetime.now() - timedelta(
                minutes=10
            )

            # Should create new cache since old one is expired
            result = get_cached_kg()

            assert result is not None
            assert result is not old_cache  # Should be a new instance


class TestSetDependencies:
    """Tests for set_dependencies function."""

    def test_set_dependencies_updates_module_globals(self) -> None:
        """Test that set_dependencies updates module-level variables."""
        mock_config = MagicMock(spec=AppConfig)
        mock_agent = MagicMock()
        mock_pipeline = MagicMock()
        mock_kg = MagicMock()

        set_dependencies(mock_config, mock_agent, mock_pipeline, mock_kg)

        # Verify module-level variables are updated
        import src.web.routers.qa_common as qa_common_module

        assert qa_common_module._config is mock_config
        assert qa_common_module.agent is mock_agent
        assert qa_common_module.pipeline is mock_pipeline
        assert qa_common_module.kg is mock_kg
