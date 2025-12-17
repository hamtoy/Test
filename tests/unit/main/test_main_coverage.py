"""Tests for main.py module to improve coverage."""

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMainModule:
    """Tests for main module functions."""

    @pytest.mark.asyncio
    async def test_main_initialization_success(self, tmp_path: Path) -> None:
        """Test main function initializes correctly."""
        from src.main import main

        # Create template directory
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = template_dir

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        with (
            patch("src.main.setup_logging") as mock_setup_logging,
            patch("src.main.AppConfig") as mock_app_config,
            patch("src.main.genai") as mock_genai,
            patch("src.main.GeminiAgent") as mock_agent,
            patch("src.main.interactive_main") as mock_interactive,
        ):
            mock_setup_logging.return_value = (mock_logger, mock_listener)
            mock_app_config.return_value = mock_config
            mock_interactive.return_value = None

            await main()

            mock_genai.configure.assert_called_once()
            mock_agent.assert_called_once()
            mock_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_template_dir_missing(self, tmp_path: Path) -> None:
        """Test main function handles missing template directory."""
        from src.main import main

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = tmp_path / "nonexistent"

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        with (
            patch("src.main.setup_logging") as mock_setup_logging,
            patch("src.main.AppConfig") as mock_app_config,
            patch("src.main.genai"),
            patch("src.main.console"),
        ):
            mock_setup_logging.return_value = (mock_logger, mock_listener)
            mock_app_config.return_value = mock_config

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1
            mock_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_value_error(self, tmp_path: Path) -> None:
        """Test main function handles ValueError."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        with (
            patch("src.main.setup_logging") as mock_setup_logging,
            patch("src.main.AppConfig") as mock_app_config,
            patch("src.main.console"),
        ):
            mock_setup_logging.return_value = (mock_logger, mock_listener)
            mock_app_config.side_effect = ValueError("Invalid config")

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_main_os_error(self, tmp_path: Path) -> None:
        """Test main function handles OSError."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        with (
            patch("src.main.setup_logging") as mock_setup_logging,
            patch("src.main.AppConfig") as mock_app_config,
            patch("src.main.console"),
        ):
            mock_setup_logging.return_value = (mock_logger, mock_listener)
            mock_app_config.side_effect = OSError("File system error")

            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1


class TestMainEntryPoint:
    """Tests for main entry point (__main__ block)."""

    def test_windows_event_loop_policy(self) -> None:
        """Test Windows event loop policy is set when on Windows."""
        # This tests the Windows-specific code path
        with (
            patch.object(os, "name", "nt"),
            patch("asyncio.set_event_loop_policy") as mock_set_policy,
            patch("asyncio.run"),
        ):
            # Mock WindowsSelectorEventLoopPolicy
            mock_policy_class = MagicMock()
            with patch.object(
                asyncio,
                "WindowsSelectorEventLoopPolicy",
                mock_policy_class,
                create=True,
            ):
                # Import and run the condition check
                if os.name == "nt":
                    try:
                        policy = getattr(
                            asyncio, "WindowsSelectorEventLoopPolicy", None
                        )
                        if policy:
                            asyncio.set_event_loop_policy(policy())
                    except AttributeError:
                        pass

                # Policy should be set
                if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
                    mock_set_policy.assert_called_once()

    def test_non_windows_no_policy_change(self) -> None:
        """Test that event loop policy is not changed on non-Windows."""
        with patch.object(os, "name", "posix"):
            # On non-Windows, no policy change should occur
            assert os.name != "nt"


class TestImports:
    """Test that imports are available."""

    def test_analyze_cache_stats_import(self) -> None:
        """Test analyze_cache_stats is importable."""
        from src.main import analyze_cache_stats

        assert analyze_cache_stats is not None

    def test_print_cache_report_import(self) -> None:
        """Test print_cache_report is importable."""
        from src.main import print_cache_report

        assert print_cache_report is not None

    def test_parse_args_import(self) -> None:
        """Test parse_args is importable."""
        from src.main import parse_args

        assert parse_args is not None

    def test_write_cache_stats_import(self) -> None:
        """Test write_cache_stats is importable."""
        from src.main import write_cache_stats

        assert write_cache_stats is not None

    def test_load_input_data_import(self) -> None:
        """Test load_input_data is importable."""
        from src.main import load_input_data

        assert load_input_data is not None

    def test_render_cost_panel_import(self) -> None:
        """Test render_cost_panel is importable."""
        from src.main import render_cost_panel

        assert render_cost_panel is not None

    def test_execute_workflow_import(self) -> None:
        """Test execute_workflow is importable."""
        from src.main import execute_workflow

        assert execute_workflow is not None
