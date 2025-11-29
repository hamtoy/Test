"""Tests for interactive_menu module to improve coverage."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import WorkflowResult
from src.ui.interactive_menu import (
    MENU_CHOICES,
    DEFAULT_OCR_PATH,
    _display_workflow_summary,
    show_cache_statistics,
    show_error_with_guide,
)


class TestShowErrorWithGuide:
    """Tests for show_error_with_guide function."""

    def test_show_error_with_guide_displays_message(self, capsys):
        """Test that show_error_with_guide displays error message and solution."""
        with patch("src.ui.interactive_menu.console") as mock_console:
            show_error_with_guide(
                error_type="테스트 오류",
                message="오류 메시지",
                solution="해결 방법",
            )
            # Should call console.print twice (error + solution)
            assert mock_console.print.call_count == 2

    def test_show_error_with_guide_formats_correctly(self):
        """Test that error guide shows correct format."""
        with patch("src.ui.interactive_menu.console") as mock_console:
            show_error_with_guide("API Error", "Key invalid", "Check .env file")
            calls = mock_console.print.call_args_list
            # First call should contain error message
            assert "API Error" in str(calls[0])
            assert "Key invalid" in str(calls[0])
            # Second call should contain solution
            assert "Check .env file" in str(calls[1])


class TestConstants:
    """Tests for module constants."""

    def test_menu_choices(self):
        """Test MENU_CHOICES constant values."""
        assert MENU_CHOICES == ["1", "2", "3", "4", "5"]
        assert len(MENU_CHOICES) == 5

    def test_default_ocr_path(self):
        """Test DEFAULT_OCR_PATH constant."""
        assert DEFAULT_OCR_PATH == "data/inputs/input_ocr.txt"
        assert "input_ocr.txt" in DEFAULT_OCR_PATH


class TestShowCacheStatistics:
    """Tests for show_cache_statistics function."""

    def test_show_cache_statistics_success(self, tmp_path):
        """Test show_cache_statistics with valid cache stats."""
        # Create mock config with cache_stats_path
        mock_config = MagicMock()
        mock_config.cache_stats_path = tmp_path / "cache_stats.json"

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.analyze_cache_stats") as mock_analyze,
            patch("src.ui.interactive_menu.print_cache_report") as mock_report,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
        ):
            mock_analyze.return_value = {"hit_rate": 0.5}
            show_cache_statistics(mock_config)

            mock_analyze.assert_called_once_with(mock_config.cache_stats_path)
            mock_report.assert_called_once()
            mock_prompt.ask.assert_called_once()

    def test_show_cache_statistics_error(self, tmp_path):
        """Test show_cache_statistics handles exceptions."""
        mock_config = MagicMock()
        mock_config.cache_stats_path = tmp_path / "nonexistent.json"

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.analyze_cache_stats") as mock_analyze,
            patch("src.ui.interactive_menu.Prompt"),
        ):
            mock_analyze.side_effect = FileNotFoundError("File not found")
            show_cache_statistics(mock_config)

            # Should print error message
            error_call = mock_console.print.call_args_list[-1]
            assert "red" in str(error_call) or "실패" in str(error_call)


class TestDisplayWorkflowSummary:
    """Tests for _display_workflow_summary function."""

    def test_display_workflow_summary_with_results(self):
        """Test _display_workflow_summary with successful results."""
        queries = ["질의 1", "질의 2", "질의 3"]

        # Create mock results
        mock_result1 = MagicMock()
        mock_result1.success = True
        mock_result2 = MagicMock()
        mock_result2.success = False
        mock_result3 = None

        results: list[WorkflowResult | None] = [
            mock_result1,
            mock_result2,
            mock_result3,
        ]

        mock_agent = MagicMock()
        mock_config = MagicMock()
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Table") as mock_table_class,
            patch("src.ui.interactive_menu.render_budget_panel") as mock_budget,
            patch("src.ui.interactive_menu.render_cost_panel") as mock_cost,
        ):
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            # Table should be created with correct columns
            mock_table.add_column.assert_called()
            # Should add rows for each query
            assert mock_table.add_row.call_count == 3
            # Should render budget and cost panels
            mock_budget.assert_called_once_with(mock_agent)
            mock_cost.assert_called_once_with(mock_agent)

    def test_display_workflow_summary_all_success(self):
        """Test _display_workflow_summary when all queries succeed."""
        queries = ["질의 1", "질의 2"]

        mock_result1 = MagicMock()
        mock_result1.success = True
        mock_result2 = MagicMock()
        mock_result2.success = True

        results = [mock_result1, mock_result2]

        mock_agent = MagicMock()
        mock_config = MagicMock()
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Table") as mock_table_class,
            patch("src.ui.interactive_menu.render_budget_panel"),
            patch("src.ui.interactive_menu.render_cost_panel"),
        ):
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            # Should print success count
            printed_args = [str(call) for call in mock_console.print.call_args_list]
            # Check that success count is displayed
            assert any("2" in arg for arg in printed_args)

    def test_display_workflow_summary_long_query(self):
        """Test _display_workflow_summary with long query text."""
        # Query longer than 50 characters should be truncated
        long_query = "이것은 매우 긴 질의입니다. " * 10

        mock_result = MagicMock()
        mock_result.success = True

        queries = [long_query]
        results = [mock_result]

        mock_agent = MagicMock()
        mock_config = MagicMock()
        timestamp = "20240101_120000"

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Table") as mock_table_class,
            patch("src.ui.interactive_menu.render_budget_panel"),
            patch("src.ui.interactive_menu.render_cost_panel"),
        ):
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table

            _display_workflow_summary(
                queries, results, mock_agent, mock_config, timestamp
            )

            # Check that add_row was called with truncated query
            call_args = mock_table.add_row.call_args
            # Second argument should be the query display
            query_display = call_args[0][1]
            assert len(query_display) <= 53  # 50 + "..."


class TestShowMainMenu:
    """Tests for show_main_menu function."""

    def test_show_main_menu_basic(self):
        """Test show_main_menu returns correct choice."""
        from src.ui.interactive_menu import show_main_menu

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch.dict(os.environ, {}, clear=True),
        ):
            mock_prompt.ask.return_value = "1"
            result = show_main_menu()
            assert result == 0  # "1" - 1 = 0

    def test_show_main_menu_with_flags(self):
        """Test show_main_menu shows feature flags when env vars set."""
        from src.ui.interactive_menu import show_main_menu

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch.dict(
                os.environ,
                {
                    "NEO4J_URI": "bolt://localhost:7687",
                    "ENABLE_LATS": "true",
                    "ENABLE_DATA2NEO": "true",
                    "REDIS_URL": "redis://localhost:6379",
                },
            ),
        ):
            mock_prompt.ask.return_value = "5"
            result = show_main_menu()
            assert result == 4  # "5" - 1 = 4

    def test_show_main_menu_all_choices(self):
        """Test show_main_menu with all choices."""
        from src.ui.interactive_menu import show_main_menu

        for choice in MENU_CHOICES:
            with (
                patch("src.ui.interactive_menu.console"),
                patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            ):
                mock_prompt.ask.return_value = choice
                result = show_main_menu()
                expected = int(choice) - 1
                assert result == expected


class TestRunWorkflowInteractive:
    """Tests for run_workflow_interactive function."""

    @pytest.mark.asyncio
    async def test_run_workflow_invalid_api_key(self):
        """Test run_workflow_interactive with invalid API key."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "invalid_key"  # Doesn't start with AIza
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
        ):
            await run_workflow_interactive(mock_agent, mock_config, mock_logger)
            # Should prompt to return to menu
            mock_prompt.ask.assert_called()

    @pytest.mark.asyncio
    async def test_run_workflow_missing_api_key(self):
        """Test run_workflow_interactive with missing API key."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = None
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
        ):
            await run_workflow_interactive(mock_agent, mock_config, mock_logger)
            mock_prompt.ask.assert_called()


class TestHandleQueryInspection:
    """Tests for _handle_query_inspection function."""

    @pytest.mark.asyncio
    async def test_handle_query_inspection_empty_query(self):
        """Test _handle_query_inspection with empty query."""
        from src.ui.interactive_menu import _handle_query_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            mock_prompt.ask.return_value = ""  # Empty query
            await _handle_query_inspection(mock_agent, mock_config)
            # Should return early for empty query

    @pytest.mark.asyncio
    async def test_handle_query_inspection_with_query(self, tmp_path):
        """Test _handle_query_inspection with valid query."""
        from src.ui.interactive_menu import _handle_query_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Create temp OCR file
        ocr_path = tmp_path / "data" / "inputs" / "input_ocr.txt"
        ocr_path.parent.mkdir(parents=True, exist_ok=True)
        ocr_path.write_text("테스트 OCR 텍스트", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_query") as mock_inspect,
            patch("src.ui.interactive_menu.DEFAULT_OCR_PATH", str(ocr_path)),
            patch.dict(os.environ, {}, clear=True),
        ):
            mock_prompt.ask.return_value = "테스트 질의"
            mock_inspect.return_value = "수정된 질의"
            await _handle_query_inspection(mock_agent, mock_config)
            mock_inspect.assert_called_once()


class TestHandleAnswerInspection:
    """Tests for _handle_answer_inspection function."""

    @pytest.mark.asyncio
    async def test_handle_answer_inspection_file_not_exists(self, tmp_path):
        """Test _handle_answer_inspection with non-existent file."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            mock_prompt.ask.return_value = str(tmp_path / "nonexistent.txt")
            await _handle_answer_inspection(mock_agent, mock_config)
            # Should print error message about file not existing
            assert any("red" in str(call) for call in mock_console.print.call_args_list)

    @pytest.mark.asyncio
    async def test_handle_answer_inspection_empty_file(self, tmp_path):
        """Test _handle_answer_inspection with empty file."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Create empty answer file
        answer_file = tmp_path / "empty_answer.txt"
        answer_file.write_text("", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            mock_prompt.ask.return_value = str(answer_file)
            await _handle_answer_inspection(mock_agent, mock_config)
            # Should print warning about empty file


class TestHandleEditMenu:
    """Tests for _handle_edit_menu function."""

    @pytest.mark.asyncio
    async def test_handle_edit_menu_file_not_exists(self, tmp_path):
        """Test _handle_edit_menu with non-existent file."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            mock_prompt.ask.return_value = str(tmp_path / "nonexistent.txt")
            await _handle_edit_menu(mock_agent, mock_config)
            # Should print error message

    @pytest.mark.asyncio
    async def test_handle_edit_menu_empty_file(self, tmp_path):
        """Test _handle_edit_menu with empty file."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        # Create empty file
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            mock_prompt.ask.return_value = str(empty_file)
            await _handle_edit_menu(mock_agent, mock_config)

    @pytest.mark.asyncio
    async def test_handle_edit_menu_empty_edit_request(self, tmp_path):
        """Test _handle_edit_menu with empty edit request."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        # Create answer file with content
        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("답변 내용", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
        ):
            # Simulate file path, no to query, then empty edit request
            mock_prompt.ask.side_effect = [str(answer_file), "", "n", ""]
            await _handle_edit_menu(mock_agent, mock_config)


class TestInteractiveMain:
    """Tests for interactive_main function."""

    @pytest.mark.asyncio
    async def test_interactive_main_exit(self):
        """Test interactive_main exits on choice 5."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.show_main_menu") as mock_menu,
        ):
            mock_menu.return_value = 4  # Choice 5 (exit)
            with pytest.raises(SystemExit) as exc_info:
                await interactive_main(mock_agent, mock_config, mock_logger)
            assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_interactive_main_keyboard_interrupt_continue(self):
        """Test interactive_main handles KeyboardInterrupt and continues."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def menu_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            return 4  # Exit on second call

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.show_main_menu") as mock_menu,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
        ):
            mock_menu.side_effect = menu_side_effect
            mock_confirm.ask.return_value = True  # Continue to main menu
            with pytest.raises(SystemExit):
                await interactive_main(mock_agent, mock_config, mock_logger)
