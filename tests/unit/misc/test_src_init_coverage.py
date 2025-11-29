"""Tests for src.__init__ module to improve coverage.

This module tests the deprecated module shims in src.__init__.py
which provide backward compatibility for legacy imports.
"""

import warnings
import pytest


class TestDeprecatedModuleShims:
    """Test deprecated module shims in src.__init__."""

    def test_gemini_model_client_shim(self) -> None:
        """Test gemini_model_client deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import gemini_model_client  # noqa: F401

            # Should emit deprecation warning
            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "gemini_model_client" in str(deprecation_warnings[0].message)

    def test_lcel_optimized_chain_shim(self) -> None:
        """Test lcel_optimized_chain deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import lcel_optimized_chain  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "lcel_optimized_chain" in str(deprecation_warnings[0].message)

    def test_list_models_shim(self) -> None:
        """Test list_models deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import list_models  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "list_models" in str(deprecation_warnings[0].message)

    def test_compare_documents_shim(self) -> None:
        """Test compare_documents deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import compare_documents  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "compare_documents" in str(deprecation_warnings[0].message)

    def test_cross_validation_shim(self) -> None:
        """Test cross_validation deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import cross_validation  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "cross_validation" in str(deprecation_warnings[0].message)

    def test_semantic_analysis_shim(self) -> None:
        """Test semantic_analysis deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import semantic_analysis  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "semantic_analysis" in str(deprecation_warnings[0].message)

    def test_custom_callback_shim(self) -> None:
        """Test custom_callback deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import custom_callback  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "custom_callback" in str(deprecation_warnings[0].message)

    def test_budget_tracker_shim(self) -> None:
        """Test budget_tracker deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import budget_tracker  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "budget_tracker" in str(deprecation_warnings[0].message)

    def test_health_check_shim(self) -> None:
        """Test health_check deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import health_check  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "health_check" in str(deprecation_warnings[0].message)

    def test_smart_autocomplete_shim(self) -> None:
        """Test smart_autocomplete deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import smart_autocomplete  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "smart_autocomplete" in str(deprecation_warnings[0].message)

    def test_dynamic_example_selector_shim(self) -> None:
        """Test dynamic_example_selector deprecated import."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src import dynamic_example_selector  # noqa: F401

            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "dynamic_example_selector" in str(deprecation_warnings[0].message)


class TestModuleNotFound:
    """Test that unknown attribute raises AttributeError."""

    def test_unknown_attribute_raises_error(self) -> None:
        """Test that accessing unknown attribute raises AttributeError."""
        import src

        with pytest.raises(AttributeError) as exc_info:
            _ = src.nonexistent_module  # noqa: B018

        assert "nonexistent_module" in str(exc_info.value)


class TestPublicAPI:
    """Test public API exports from src."""

    def test_version_exists(self) -> None:
        """Test that __version__ is exported."""
        import src

        assert hasattr(src, "__version__")
        assert src.__version__ == "3.0.0"

    def test_gemini_agent_export(self) -> None:
        """Test that GeminiAgent is exported."""
        from src import GeminiAgent

        assert GeminiAgent is not None

    def test_app_config_export(self) -> None:
        """Test that AppConfig is exported."""
        from src import AppConfig

        assert AppConfig is not None

    def test_exceptions_export(self) -> None:
        """Test that exceptions are exported."""
        from src import BudgetExceededError, APIRateLimitError, ValidationFailedError

        assert BudgetExceededError is not None
        assert APIRateLimitError is not None
        assert ValidationFailedError is not None

    def test_models_export(self) -> None:
        """Test that models are exported."""
        from src import WorkflowResult, EvaluationResultSchema, QueryResult

        assert WorkflowResult is not None
        assert EvaluationResultSchema is not None
        assert QueryResult is not None

    def test_all_contains_expected_names(self) -> None:
        """Test that __all__ contains expected names."""
        import src

        assert "__version__" in src.__all__
        assert "GeminiAgent" in src.__all__
        assert "AppConfig" in src.__all__
        assert "WorkflowResult" in src.__all__
