"""Tests for src/ui/interactive_menu.py to improve coverage."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest


class TestShowErrorWithGuide:
    """Tests for show_error_with_guide function."""

    def test_show_error_with_guide(self, capsys):
        """Test error message display."""
        from src.ui.interactive_menu import show_error_with_guide

        with patch("src.ui.interactive_menu.console") as mock_console:
            show_error_with_guide("Test Error", "Error message", "Try this solution")

            # Check console.print was called with error info
            assert mock_console.print.called


class TestDisplayWorkflowSummary:
    """Tests for _display_workflow_summary function."""

    def test_display_workflow_summary_with_success(self):
        """Test workflow summary display with successful results."""
        from src.ui.interactive_menu import _display_workflow_summary
        from src.core.models import WorkflowResult

        # Mock dependencies
        mock_agent = MagicMock()
        mock_config = MagicMock()

        # Create test data
        queries = ["query1", "query2"]
        result1 = MagicMock(spec=WorkflowResult)
        result1.success = True
        result2 = MagicMock(spec=WorkflowResult)
        result2.success = False
        results = [result1, result2]
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.render_budget_panel") as mock_budget,
            patch("src.ui.interactive_menu.render_cost_panel") as mock_cost,
        ):
            mock_budget.return_value = MagicMock()
            mock_cost.return_value = MagicMock()

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            # Check that console.print was called
            assert mock_console.print.called

    def test_display_workflow_summary_long_query(self):
        """Test workflow summary with long query text."""
        from src.ui.interactive_menu import _display_workflow_summary
        from src.core.models import WorkflowResult

        mock_agent = MagicMock()
        mock_config = MagicMock()

        # Long query that should be truncated
        long_query = "a" * 100
        queries = [long_query]
        result = MagicMock(spec=WorkflowResult)
        result.success = True
        results = [result]
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.render_budget_panel") as mock_budget,
            patch("src.ui.interactive_menu.render_cost_panel") as mock_cost,
        ):
            mock_budget.return_value = MagicMock()
            mock_cost.return_value = MagicMock()

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            assert mock_console.print.called

    def test_display_workflow_summary_all_failed(self):
        """Test workflow summary with all failed results."""
        from src.ui.interactive_menu import _display_workflow_summary

        mock_agent = MagicMock()
        mock_config = MagicMock()

        queries = ["query1", "query2"]
        results = [None, None]  # All failed
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.render_budget_panel") as mock_budget,
            patch("src.ui.interactive_menu.render_cost_panel") as mock_cost,
        ):
            mock_budget.return_value = MagicMock()
            mock_cost.return_value = MagicMock()

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            assert mock_console.print.called


class TestShowCacheStatistics:
    """Tests for show_cache_statistics function."""

    def test_show_cache_statistics_success(self):
        """Test cache statistics display."""
        from src.ui.interactive_menu import show_cache_statistics

        mock_config = MagicMock()
        mock_config.cache_stats_path = Path("/tmp/test_cache.jsonl")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.analyze_cache_stats") as mock_analyze,
            patch("src.ui.interactive_menu.print_cache_report") as mock_report,
            patch("src.ui.interactive_menu.Prompt.ask", return_value=""),
        ):
            mock_analyze.return_value = {"hits": 10, "misses": 5}

            show_cache_statistics(mock_config)

            mock_analyze.assert_called_once()
            mock_report.assert_called_once()

    def test_show_cache_statistics_error(self):
        """Test cache statistics display with error."""
        from src.ui.interactive_menu import show_cache_statistics

        mock_config = MagicMock()
        mock_config.cache_stats_path = Path("/tmp/test_cache.jsonl")

        with patch("src.ui.interactive_menu.console") as mock_console, patch(
            "src.ui.interactive_menu.analyze_cache_stats",
            side_effect=Exception("File not found"),
        ), patch("src.ui.interactive_menu.Prompt.ask", return_value=""):
            show_cache_statistics(mock_config)

            # Should print error message
            assert any(
                "실패" in str(call) or "failed" in str(call).lower()
                for call in mock_console.print.call_args_list
            )


class TestConstants:
    """Tests for module constants."""

    def test_menu_choices(self):
        """Test MENU_CHOICES constant."""
        from src.ui.interactive_menu import MENU_CHOICES

        assert MENU_CHOICES == ["1", "2", "3", "4", "5"]

    def test_default_ocr_path(self):
        """Test DEFAULT_OCR_PATH constant."""
        from src.ui.interactive_menu import DEFAULT_OCR_PATH

        assert DEFAULT_OCR_PATH == "data/inputs/input_ocr.txt"


class TestShowMainMenu:
    """Tests for show_main_menu function."""

    def test_show_main_menu_basic(self, monkeypatch):
        """Test main menu display."""
        from src.ui.interactive_menu import show_main_menu

        # Clear environment variables
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("ENABLE_LATS", raising=False)
        monkeypatch.delenv("ENABLE_DATA2NEO", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt.ask", return_value="1"),
        ):
            result = show_main_menu()

            assert result == 0  # Choice "1" returns 0 (index)
            assert mock_console.clear.called

    def test_show_main_menu_with_flags(self, monkeypatch):
        """Test main menu with feature flags enabled."""
        from src.ui.interactive_menu import show_main_menu

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("ENABLE_LATS", "true")
        monkeypatch.setenv("ENABLE_DATA2NEO", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt.ask", return_value="5"),
        ):
            result = show_main_menu()

            assert result == 4  # Choice "5" returns 4 (index)


class TestInteractiveMain:
    """Tests for interactive_main function."""

    @pytest.mark.asyncio
    async def test_interactive_main_exit(self):
        """Test interactive main exits on choice 5."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.show_main_menu", return_value=4),
            patch("src.ui.interactive_menu.console"),
            pytest.raises(SystemExit) as exc,
        ):
            await interactive_main(mock_agent, mock_config, mock_logger)
        assert exc.value.code == 0

    @pytest.mark.asyncio
    async def test_interactive_main_keyboard_interrupt_exit(self):
        """Test interactive main handles KeyboardInterrupt and exits."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Confirm.ask", return_value=False),
            pytest.raises(SystemExit) as exc,
        ):
            await interactive_main(mock_agent, mock_config, mock_logger)
        assert exc.value.code == 0

    @pytest.mark.asyncio
    async def test_interactive_main_keyboard_interrupt_continue(self):
        """Test interactive main handles KeyboardInterrupt and continues."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            return 4  # Exit on second call

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Confirm.ask", return_value=True),
            pytest.raises(SystemExit) as exc,
        ):
            await interactive_main(mock_agent, mock_config, mock_logger)
        assert exc.value.code == 0

    @pytest.mark.asyncio
    async def test_interactive_main_unexpected_error(self):
        """Test interactive main handles unexpected errors."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Unexpected error")
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt.ask", return_value=""),
            pytest.raises(SystemExit) as exc,
        ):
            await interactive_main(mock_agent, mock_config, mock_logger)
        assert exc.value.code == 0

    @pytest.mark.asyncio
    async def test_interactive_main_cache_statistics_choice(self):
        """Test interactive main handles cache statistics choice."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 3  # Cache statistics
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.show_cache_statistics") as mock_cache,
            pytest.raises(SystemExit),
        ):
            await interactive_main(mock_agent, mock_config, mock_logger)
        mock_cache.assert_called_once()


class TestRunWorkflowInteractive:
    """Tests for run_workflow_interactive function."""

    @pytest.mark.asyncio
    async def test_run_workflow_invalid_api_key(self):
        """Test workflow with invalid API key."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = None  # Invalid
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.show_error_with_guide"),
            patch("src.ui.interactive_menu.Prompt.ask", return_value=""),
        ):
            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

    @pytest.mark.asyncio
    async def test_run_workflow_invalid_api_key_format(self):
        """Test workflow with invalid API key format."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "invalid_key"  # Wrong format
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.show_error_with_guide") as mock_error,
            patch("src.ui.interactive_menu.Prompt.ask", return_value=""),
        ):
            await run_workflow_interactive(mock_agent, mock_config, mock_logger)
            mock_error.assert_called()
