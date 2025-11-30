"""Tests for src/analytics/__init__.py lazy import coverage."""

import pytest


class TestAnalyticsPackageLazyImports:
    """Test lazy imports in src.analytics package."""

    def test_usage_dashboard_lazy_import(self) -> None:
        """Test lazy import of UsageDashboard."""
        from src.analytics import UsageDashboard

        assert UsageDashboard is not None
        assert hasattr(UsageDashboard, "__init__")

    def test_unknown_attribute_raises_error(self) -> None:
        """Test that unknown attribute raises AttributeError."""
        import src.analytics

        with pytest.raises(AttributeError) as exc_info:
            _ = src.analytics.nonexistent_function  # noqa: B018

        assert "nonexistent_function" in str(exc_info.value)
        assert "src.analytics" in str(exc_info.value)

    def test_all_exports(self) -> None:
        """Test that __all__ contains expected exports."""
        import src.analytics

        assert "UsageDashboard" in src.analytics.__all__
