"""Comprehensive tests for src/ui module to achieve full coverage.

This module provides tests for:
- src/ui/__init__.py: lazy import functionality
- src/ui/interactive_menu.py: complete workflow testing

Testing Strategy:
1. Mocking: All external dependencies (Agent, Workflow, API) are mocked
2. I/O Capture: Uses monkeypatch for input, capsys for output
3. Scenarios: Success cases, error cases, and edge cases
4. Type Safety: All functions have proper type hints for mypy strict mode
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestUIPackageInit:
    """Tests for src/ui/__init__.py lazy import functionality."""

    def test_lazy_import_interactive_main(self) -> None:
        """Test __getattr__ lazy import for interactive_main."""
        # Import the module fresh to test lazy import
        import src.ui

        # Access interactive_main via lazy import
        result = src.ui.interactive_main
        assert callable(result)

    def test_getattr_unknown_attribute_raises(self) -> None:
        """Test __getattr__ raises AttributeError for unknown attributes."""
        import src.ui

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = getattr(src.ui, "nonexistent_function")

    def test_exported_symbols(self) -> None:
        """Test all __all__ symbols are accessible."""
        from src.ui import (
            console,
            display_queries,
            interactive_main,
            render_budget_panel,
            render_cost_panel,
        )

        assert console is not None
        assert callable(display_queries)
        assert callable(interactive_main)
        assert callable(render_budget_panel)
        assert callable(render_cost_panel)


class TestRunWorkflowInteractiveSuccess:
    """Tests for run_workflow_interactive successful paths."""

    @pytest.mark.asyncio
    async def test_run_workflow_file_creation_ocr(self, tmp_path: Path) -> None:
        """Test run_workflow creates OCR file when missing and user confirms."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
        ):
            # Setup: OCR file doesn't exist, user confirms creation
            mock_prompt.ask.side_effect = ["input_ocr.txt", "input_candidates.json"]
            mock_confirm.ask.return_value = False  # Don't create, return early

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)
            # Verify confirm was asked
            assert mock_confirm.ask.called

    @pytest.mark.asyncio
    async def test_run_workflow_file_creation_candidates(self, tmp_path: Path) -> None:
        """Test run_workflow creates candidate file when missing and user confirms."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create OCR file but not candidates
        ocr_path = tmp_path / "input_ocr.txt"
        ocr_path.write_text("OCR content", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
        ):
            mock_prompt.ask.side_effect = ["input_ocr.txt", "input_candidates.json"]
            mock_confirm.ask.return_value = False  # Don't create, return early

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)
            assert mock_confirm.ask.called

    @pytest.mark.asyncio
    async def test_run_workflow_file_creation_actually_creates_ocr(
        self, tmp_path: Path
    ) -> None:
        """Test OCR file is actually created when user confirms."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
        ):
            # Setup: First confirm for OCR creation, then reject candidates
            mock_prompt.ask.side_effect = ["input_ocr.txt", "input_candidates.json"]
            mock_confirm.ask.side_effect = [
                True,
                False,
            ]  # Create OCR, don't create cand

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            # Verify OCR file was created
            ocr_path = tmp_path / "input_ocr.txt"
            assert ocr_path.exists()

    @pytest.mark.asyncio
    async def test_run_workflow_file_creation_actually_creates_candidates(
        self, tmp_path: Path
    ) -> None:
        """Test candidates file is actually created with template."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=[])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create OCR file
        ocr_path = tmp_path / "input_ocr.txt"
        ocr_path.write_text("OCR content", encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
            ]
            mock_confirm.ask.return_value = True  # Create template
            mock_load.return_value = ("OCR content", {"a": "Answer"})

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            # Verify candidates file was created
            cand_path = tmp_path / "input_candidates.json"
            assert cand_path.exists()
            content = json.loads(cand_path.read_text(encoding="utf-8"))
            assert "a" in content

    @pytest.mark.asyncio
    async def test_run_workflow_data_load_file_not_found(self, tmp_path: Path) -> None:
        """Test run_workflow handles FileNotFoundError during data load."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.show_error_with_guide") as mock_error,
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # return after error
            ]
            mock_load.side_effect = FileNotFoundError("File not found")

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            # Verify error was shown
            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_run_workflow_data_load_json_error(self, tmp_path: Path) -> None:
        """Test run_workflow handles JSON parse error during data load."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.show_error_with_guide") as mock_error,
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # return after error
            ]
            # Create exception with JSON decode cause
            exc = Exception("Load error")
            exc.__cause__ = json.JSONDecodeError("error", "", 0)
            mock_load.side_effect = exc

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            mock_error.assert_called()
            # Check that JSON error was detected
            call_args = mock_error.call_args
            assert "JSON" in str(call_args)

    @pytest.mark.asyncio
    async def test_run_workflow_data_load_general_error(self, tmp_path: Path) -> None:
        """Test run_workflow handles general error during data load."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.show_error_with_guide") as mock_error,
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # return after error
            ]
            mock_load.side_effect = ValueError("Some other error")

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_run_workflow_empty_queries(self, tmp_path: Path) -> None:
        """Test run_workflow handles empty query generation."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=[])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
            ]
            mock_load.return_value = ("OCR content", {"a": "Answer"})

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            # Check that "생성된 질의가 없습니다" was printed
            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("질의가 없습니다" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_run_workflow_query_generation_error(self, tmp_path: Path) -> None:
        """Test run_workflow handles query generation exception."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(side_effect=RuntimeError("API Error"))
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.show_error_with_guide") as mock_error,
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
                "",  # return after error
            ]
            mock_load.return_value = ("OCR content", {"a": "Answer"})

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_run_workflow_user_cancels_queries(self, tmp_path: Path) -> None:
        """Test run_workflow when user cancels proceeding with queries."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["Query 1", "Query 2"])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.display_queries"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
            ]
            mock_confirm.ask.return_value = False  # Cancel
            mock_load.return_value = ("OCR content", {"a": "Answer"})

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("취소" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_run_workflow_full_success(self, tmp_path: Path) -> None:
        """Test run_workflow complete success path with workflow execution."""
        from src.ui.interactive_menu import run_workflow_interactive
        from src.core.models import WorkflowResult

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        # Create mock workflow result
        mock_result = MagicMock(spec=WorkflowResult)
        mock_result.success = True

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.display_queries"),
            patch("src.ui.interactive_menu.execute_workflow_simple") as mock_exec,
            patch("src.ui.interactive_menu._display_workflow_summary"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
                "",  # return at end
            ]
            mock_confirm.ask.return_value = True
            mock_load.return_value = ("OCR content", {"a": "Answer"})
            mock_exec.return_value = mock_result

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_workflow_result_not_success(self, tmp_path: Path) -> None:
        """Test run_workflow handles unsuccessful workflow result."""
        from src.ui.interactive_menu import run_workflow_interactive
        from src.core.models import WorkflowResult

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        # Create mock workflow result with success=False
        mock_result = MagicMock(spec=WorkflowResult)
        mock_result.success = False

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.display_queries"),
            patch("src.ui.interactive_menu.execute_workflow_simple") as mock_exec,
            patch("src.ui.interactive_menu._display_workflow_summary"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
                "",  # return at end
            ]
            mock_confirm.ask.return_value = True
            mock_load.return_value = ("OCR content", {"a": "Answer"})
            mock_exec.return_value = mock_result

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

    @pytest.mark.asyncio
    async def test_run_workflow_execution_error(self, tmp_path: Path) -> None:
        """Test run_workflow handles exception during workflow execution."""
        from src.ui.interactive_menu import run_workflow_interactive

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "x" * 35
        mock_config.input_dir = tmp_path
        mock_logger = MagicMock()

        # Create both files
        (tmp_path / "input_ocr.txt").write_text("OCR", encoding="utf-8")
        (tmp_path / "input_candidates.json").write_text('{"a":"A"}', encoding="utf-8")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Confirm") as mock_confirm,
            patch("src.ui.interactive_menu.load_input_data") as mock_load,
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.display_queries"),
            patch("src.ui.interactive_menu.execute_workflow_simple") as mock_exec,
            patch("src.ui.interactive_menu._display_workflow_summary"),
        ):
            mock_prompt.ask.side_effect = [
                "input_ocr.txt",
                "input_candidates.json",
                "",  # user_intent
                "",  # return at end
            ]
            mock_confirm.ask.return_value = True
            mock_load.return_value = ("OCR content", {"a": "Answer"})
            mock_exec.side_effect = RuntimeError("Execution failed")

            await run_workflow_interactive(mock_agent, mock_config, mock_logger)

            mock_logger.exception.assert_called()


class TestHandleQueryInspectionComplete:
    """Complete tests for _handle_query_inspection function."""

    @pytest.mark.asyncio
    async def test_query_inspection_no_ocr_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test query inspection when OCR file doesn't exist."""
        from src.ui.interactive_menu import _handle_query_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Make sure DEFAULT_OCR_PATH points to non-existent file
        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_query") as mock_inspect,
        ):
            mock_prompt.ask.return_value = "테스트 질의"
            mock_inspect.return_value = "수정된 질의"

            await _handle_query_inspection(mock_agent, mock_config)

            # Verify OCR file not found message was printed
            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("OCR 파일 없음" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_query_inspection_with_redis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test query inspection with Redis cache enabled."""
        from src.ui.interactive_menu import _handle_query_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_query") as mock_inspect,
            patch("src.ui.interactive_menu.RedisEvalCache") as mock_redis,
        ):
            mock_prompt.ask.return_value = "테스트 질의"
            mock_inspect.return_value = "수정된 질의"
            mock_redis.return_value = MagicMock()

            await _handle_query_inspection(mock_agent, mock_config)

            mock_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_inspection_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test query inspection handles exceptions."""
        from src.ui.interactive_menu import _handle_query_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_query") as mock_inspect,
        ):
            mock_prompt.ask.return_value = "테스트 질의"
            mock_inspect.side_effect = RuntimeError("Inspection failed")

            await _handle_query_inspection(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("실패" in call for call in print_calls)


class TestHandleAnswerInspectionComplete:
    """Complete tests for _handle_answer_inspection function."""

    @pytest.mark.asyncio
    async def test_answer_inspection_no_ocr_file_with_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test answer inspection when OCR file doesn't exist and user provides path."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Create answer file
        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Test answer content", encoding="utf-8")

        # Create alternate OCR file
        alt_ocr = tmp_path / "alt_ocr.txt"
        alt_ocr.write_text("Alternate OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_answer") as mock_inspect,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file path
                str(alt_ocr),  # OCR file path
                "n",  # no query
            ]
            mock_inspect.return_value = "Fixed answer"

            await _handle_answer_inspection(mock_agent, mock_config)

            mock_inspect.assert_called_once()

    @pytest.mark.asyncio
    async def test_answer_inspection_no_ocr_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test answer inspection when user-provided OCR path doesn't exist."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Create answer file
        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Test answer content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_answer") as mock_inspect,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file path
                str(tmp_path / "nonexistent.txt"),  # Non-existent OCR path
                "n",  # no query
            ]
            mock_inspect.return_value = "Fixed answer"

            await _handle_answer_inspection(mock_agent, mock_config)

            # Verify warning was printed
            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("찾을 수 없습니다" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_answer_inspection_with_query(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test answer inspection with query input."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        # Create answer file and OCR file
        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Test answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_answer") as mock_inspect,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file path
                "y",  # yes to query
                "Test query",  # query content
            ]
            mock_inspect.return_value = "Fixed answer"

            await _handle_answer_inspection(mock_agent, mock_config)

            # Verify inspect_answer was called with query
            call_args = mock_inspect.call_args
            assert "Test query" in str(call_args)

    @pytest.mark.asyncio
    async def test_answer_inspection_with_redis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test answer inspection with Redis cache enabled."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Test answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_answer") as mock_inspect,
            patch("src.ui.interactive_menu.RedisEvalCache") as mock_redis,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),
                "n",  # no query
            ]
            mock_inspect.return_value = "Fixed answer"
            mock_redis.return_value = MagicMock()

            await _handle_answer_inspection(mock_agent, mock_config)

            mock_redis.assert_called_once()

    @pytest.mark.asyncio
    async def test_answer_inspection_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test answer inspection handles exceptions."""
        from src.ui.interactive_menu import _handle_answer_inspection

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None
        mock_config.enable_lats = False

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Test answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )
        monkeypatch.delenv("REDIS_URL", raising=False)

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.inspect_answer") as mock_inspect,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),
                "n",
            ]
            mock_inspect.side_effect = RuntimeError("Inspection failed")

            await _handle_answer_inspection(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("실패" in call for call in print_calls)


class TestHandleEditMenuComplete:
    """Complete tests for _handle_edit_menu function."""

    @pytest.mark.asyncio
    async def test_edit_menu_no_ocr_with_path_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu when OCR doesn't exist and user provides path."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        # Create answer file and alternate OCR
        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")
        alt_ocr = tmp_path / "alt_ocr.txt"
        alt_ocr.write_text("Alternate OCR", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file
                str(alt_ocr),  # OCR file path
                "n",  # no query
                "Fix grammar",  # edit request
            ]
            mock_edit.return_value = "Edited content"

            await _handle_edit_menu(mock_agent, mock_config)

            mock_edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_edit_menu_no_ocr_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu when user-provided OCR path doesn't exist."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file
                str(tmp_path / "nonexistent.txt"),  # non-existent OCR
                "n",  # no query
                "Fix grammar",  # edit request
            ]
            mock_edit.return_value = "Edited content"

            await _handle_edit_menu(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("찾을 수 없습니다" in call for call in print_calls)
            assert any("OCR 텍스트 없음" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_edit_menu_no_ocr_empty_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu when user provides empty OCR path."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(tmp_path / "nonexistent_ocr.txt"),
        )

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file
                "",  # empty OCR path
                "n",  # no query
                "Fix grammar",  # edit request
            ]
            mock_edit.return_value = "Edited content"

            await _handle_edit_menu(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("OCR 텍스트 없음" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_edit_menu_with_query(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu with query input."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )

        with (
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file
                "y",  # yes to query
                "Test query",  # query content
                "Fix grammar",  # edit request
            ]
            mock_edit.return_value = "Edited content"

            await _handle_edit_menu(mock_agent, mock_config)

            call_args = mock_edit.call_args
            assert call_args.kwargs.get("query") == "Test query"

    @pytest.mark.asyncio
    async def test_edit_menu_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu complete success path."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),  # answer file
                "n",  # no query
                "Fix grammar",  # edit request
            ]
            mock_edit.return_value = "Edited content"

            await _handle_edit_menu(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("완료" in call for call in print_calls)
            assert any("저장됨" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_edit_menu_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit menu handles exceptions."""
        from src.ui.interactive_menu import _handle_edit_menu

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_config.neo4j_uri = None

        answer_file = tmp_path / "answer.txt"
        answer_file.write_text("Answer content", encoding="utf-8")
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("OCR content", encoding="utf-8")

        monkeypatch.setattr(
            "src.ui.interactive_menu.DEFAULT_OCR_PATH",
            str(ocr_file),
        )

        with (
            patch("src.ui.interactive_menu.console") as mock_console,
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu.Panel"),
            patch("src.ui.interactive_menu.Progress"),
            patch("src.ui.interactive_menu.edit_content") as mock_edit,
        ):
            mock_prompt.ask.side_effect = [
                str(answer_file),
                "n",
                "Fix grammar",
            ]
            mock_edit.side_effect = RuntimeError("Edit failed")

            await _handle_edit_menu(mock_agent, mock_config)

            print_calls = [str(c) for c in mock_console.print.call_args_list]
            assert any("오류 발생" in call for call in print_calls)


class TestInteractiveMainComplete:
    """Complete tests for interactive_main function."""

    @pytest.mark.asyncio
    async def test_interactive_main_workflow_choice(self) -> None:
        """Test interactive main handles workflow choice (option 1)."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu() -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0  # Workflow
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.run_workflow_interactive") as mock_wf,
            pytest.raises(SystemExit),
        ):
            mock_wf.return_value = None
            await interactive_main(mock_agent, mock_config, mock_logger)
        mock_wf.assert_called_once()

    @pytest.mark.asyncio
    async def test_interactive_main_inspection_query_choice(self) -> None:
        """Test interactive main handles inspection query choice (option 2-1)."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu() -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1  # Inspection
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu._handle_query_inspection") as mock_qi,
            pytest.raises(SystemExit),
        ):
            mock_prompt.ask.return_value = "1"  # Query inspection
            mock_qi.return_value = None
            await interactive_main(mock_agent, mock_config, mock_logger)
        mock_qi.assert_called_once()

    @pytest.mark.asyncio
    async def test_interactive_main_inspection_answer_choice(self) -> None:
        """Test interactive main handles inspection answer choice (option 2-2)."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu() -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1  # Inspection
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu.Prompt") as mock_prompt,
            patch("src.ui.interactive_menu._handle_answer_inspection") as mock_ai,
            pytest.raises(SystemExit),
        ):
            mock_prompt.ask.return_value = "2"  # Answer inspection
            mock_ai.return_value = None
            await interactive_main(mock_agent, mock_config, mock_logger)
        mock_ai.assert_called_once()

    @pytest.mark.asyncio
    async def test_interactive_main_edit_choice(self) -> None:
        """Test interactive main handles edit choice (option 3)."""
        from src.ui.interactive_menu import interactive_main

        mock_agent = MagicMock()
        mock_config = MagicMock()
        mock_logger = MagicMock()

        call_count = 0

        def mock_show_menu() -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 2  # Edit
            return 4  # Exit

        with (
            patch("src.ui.interactive_menu.show_main_menu", side_effect=mock_show_menu),
            patch("src.ui.interactive_menu.console"),
            patch("src.ui.interactive_menu._handle_edit_menu") as mock_edit,
            pytest.raises(SystemExit),
        ):
            mock_edit.return_value = None
            await interactive_main(mock_agent, mock_config, mock_logger)
        mock_edit.assert_called_once()
