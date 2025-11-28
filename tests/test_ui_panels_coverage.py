"""Tests for src/ui/panels.py to improve coverage."""

from unittest.mock import MagicMock
from rich.panel import Panel


class TestRenderCostPanel:
    """Test render_cost_panel function."""

    def test_render_cost_panel_with_get_total_cost(self):
        """Test render_cost_panel when agent has get_total_cost method."""
        from src.ui.panels import render_cost_panel

        mock_agent = MagicMock()
        mock_agent.get_total_cost.return_value = 0.0123
        mock_agent.total_input_tokens = 1000
        mock_agent.total_output_tokens = 500
        mock_agent.cache_hits = 10
        mock_agent.cache_misses = 5

        result = render_cost_panel(mock_agent)

        assert isinstance(result, Panel)
        mock_agent.get_total_cost.assert_called_once()

    def test_render_cost_panel_without_get_total_cost(self):
        """Test render_cost_panel when agent lacks get_total_cost method."""
        from src.ui.panels import render_cost_panel

        mock_agent = MagicMock(spec=[])  # No methods
        mock_agent.total_input_tokens = 1000
        mock_agent.total_output_tokens = 500
        mock_agent.cache_hits = 10
        mock_agent.cache_misses = 5

        result = render_cost_panel(mock_agent)

        assert isinstance(result, Panel)


class TestRenderBudgetPanel:
    """Test render_budget_panel function."""

    def test_render_budget_panel_with_method(self):
        """Test render_budget_panel when agent has get_budget_usage_percent."""
        from src.ui.panels import render_budget_panel

        mock_agent = MagicMock()
        mock_agent.get_budget_usage_percent.return_value = 45.5

        result = render_budget_panel(mock_agent)

        assert isinstance(result, Panel)
        mock_agent.get_budget_usage_percent.assert_called_once()

    def test_render_budget_panel_without_method(self):
        """Test render_budget_panel when agent lacks the method."""
        from src.ui.panels import render_budget_panel

        mock_agent = MagicMock(spec=[])  # No methods

        result = render_budget_panel(mock_agent)

        assert isinstance(result, Panel)


class TestDisplayQueries:
    """Test display_queries function."""

    def test_display_queries(self, capsys):
        """Test display_queries outputs correctly."""
        from src.ui.panels import display_queries

        queries = ["첫 번째 질의", "두 번째 질의", "세 번째 질의"]

        display_queries(queries)

        # Just verify it doesn't raise an error
        # Rich console output is complex to capture

    def test_display_queries_empty(self):
        """Test display_queries with empty list."""
        from src.ui.panels import display_queries

        queries = []

        # Should not raise an error
        display_queries(queries)


class TestConsoleExport:
    """Test console export."""

    def test_console_is_available(self):
        """Test console is exported and usable."""
        from src.ui.panels import console

        assert console is not None
        assert hasattr(console, "print")
