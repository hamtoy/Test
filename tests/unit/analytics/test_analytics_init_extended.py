"""Comprehensive tests for analytics/__init__.py module."""
# mypy: ignore-errors

import pytest


class TestAnalyticsInit:
    """Tests for analytics package lazy imports."""

    def test_getattr_usage_dashboard(self):
        """Test lazy import of UsageDashboard."""
        from src.analytics import UsageDashboard

        assert UsageDashboard is not None
        # Verify it's the correct class
        assert UsageDashboard.__name__ == "UsageDashboard"

    def test_getattr_realtime_dashboard(self):
        """Test lazy import of RealtimeDashboard."""
        from src.analytics import RealtimeDashboard

        assert RealtimeDashboard is not None
        assert RealtimeDashboard.__name__ == "RealtimeDashboard"

    def test_getattr_get_dashboard(self):
        """Test lazy import of get_dashboard function."""
        from src.analytics import get_dashboard

        assert get_dashboard is not None
        assert callable(get_dashboard)

    def test_getattr_invalid_attribute(self):
        """Test that invalid attribute raises AttributeError."""
        import src.analytics as analytics

        with pytest.raises(AttributeError) as exc_info:
            _ = analytics.NonExistentClass

        assert "has no attribute 'NonExistentClass'" in str(exc_info.value)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from src.analytics import __all__

        assert "UsageDashboard" in __all__
        assert "RealtimeDashboard" in __all__
        assert "get_dashboard" in __all__
        assert len(__all__) == 3

    def test_multiple_imports(self):
        """Test that multiple imports return the same class."""
        from src.analytics import RealtimeDashboard as RD1
        from src.analytics import RealtimeDashboard as RD2

        assert RD1 is RD2

    def test_import_all_exports(self):
        """Test importing all exported names."""
        from src.analytics import UsageDashboard, RealtimeDashboard, get_dashboard

        assert all([UsageDashboard, RealtimeDashboard, get_dashboard])
