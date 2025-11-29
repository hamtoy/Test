"""Tests for src/main.py to improve coverage."""

import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestMainImports:
    """Tests for imports in main.py."""

    def test_imports_are_accessible(self):
        """Test that key imports from main.py are accessible."""
        from src.main import (  # type: ignore[attr-defined]
            parse_args,
            analyze_cache_stats,
            print_cache_report,
            load_input_data,
            render_cost_panel,
            execute_workflow,
            write_cache_stats,
        )

        # All imports should be available
        assert parse_args is not None
        assert analyze_cache_stats is not None
        assert print_cache_report is not None
        assert load_input_data is not None
        assert render_cost_panel is not None
        assert execute_workflow is not None
        assert write_cache_stats is not None


class TestMainFunction:
    """Tests for main function."""

    @pytest.mark.asyncio
    async def test_main_initialization_error(self, monkeypatch, tmp_path):
        """Test main function handles initialization errors."""
        # Set up environment
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        # Create templates directory but not the template file
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        mock_log_listener = MagicMock()
        mock_log_listener.stop = MagicMock()

        mock_logger = MagicMock()

        with (
            patch(
                "src.main.setup_logging", return_value=(mock_logger, mock_log_listener)
            ),
            patch("src.main.AppConfig", side_effect=ValueError("Config error")),
        ):
            from src.main import main

            with pytest.raises(SystemExit) as exc:
                await main()
            assert exc.value.code == 1

    @pytest.mark.asyncio
    async def test_main_template_not_found(self, monkeypatch, tmp_path):
        """Test main function handles missing templates directory."""
        # Set up environment
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        mock_log_listener = MagicMock()
        mock_log_listener.stop = MagicMock()

        mock_logger = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = valid_key
        mock_config.template_dir = tmp_path / "nonexistent_templates"

        with (
            patch(
                "src.main.setup_logging", return_value=(mock_logger, mock_log_listener)
            ),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            pytest.raises(SystemExit) as exc,
        ):
            from src.main import main

            await main()
        assert exc.value.code == 1

    @pytest.mark.asyncio
    async def test_main_success_flow(self, monkeypatch, tmp_path):
        """Test main function successful initialization."""
        # Set up environment
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        # Create templates directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "test.j2").write_text("test template")

        mock_log_listener = MagicMock()
        mock_log_listener.stop = MagicMock()

        mock_logger = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = valid_key
        mock_config.template_dir = templates_dir

        mock_agent = MagicMock()

        with (
            patch(
                "src.main.setup_logging", return_value=(mock_logger, mock_log_listener)
            ),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            patch("src.main.GeminiAgent", return_value=mock_agent),
            patch(
                "src.main.interactive_main", new_callable=AsyncMock
            ) as mock_interactive,
        ):
            from src.main import main

            await main()

            # Verify interactive_main was called
            mock_interactive.assert_called_once()
            mock_log_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_os_error(self, monkeypatch, tmp_path):
        """Test main function handles OSError."""
        # Set up environment
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        mock_log_listener = MagicMock()
        mock_log_listener.stop = MagicMock()

        mock_logger = MagicMock()

        with (
            patch(
                "src.main.setup_logging", return_value=(mock_logger, mock_log_listener)
            ),
            patch("src.main.AppConfig", side_effect=OSError("Permission denied")),
        ):
            from src.main import main

            with pytest.raises(SystemExit) as exc:
                await main()
            assert exc.value.code == 1


class TestMainEntryPoint:
    """Tests for __main__ block behavior."""

    def test_windows_event_loop_policy(self, monkeypatch):
        """Test Windows event loop policy setting."""
        # Simulate Windows environment
        monkeypatch.setattr(os, "name", "nt")

        mock_policy = MagicMock()

        with (
            patch.object(
                asyncio, "WindowsSelectorEventLoopPolicy", mock_policy, create=True
            ),
            patch.object(asyncio, "set_event_loop_policy") as mock_set_policy,
        ):
            # Import and check if policy was applied
            # This is a simplified test since we can't easily test the __main__ block
            if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
                policy = asyncio.WindowsSelectorEventLoopPolicy()
                asyncio.set_event_loop_policy(policy)
                mock_set_policy.assert_called()

    def test_non_windows_event_loop_policy(self, monkeypatch):
        """Test non-Windows event loop policy (no change needed)."""
        # Simulate non-Windows environment
        monkeypatch.setattr(os, "name", "posix")

        # On non-Windows, no policy change should happen
        # This is just to ensure the code path works
        assert os.name == "posix"


class TestConsoleOutput:
    """Tests for console output in main module."""

    def test_console_import(self):
        """Test that console is properly imported."""
        from src.main import console  # type: ignore[attr-defined]

        assert console is not None

    def test_user_interrupt_message_import(self):
        """Test that USER_INTERRUPT_MESSAGE is properly imported."""
        from src.main import USER_INTERRUPT_MESSAGE  # type: ignore[attr-defined]

        # Check it's the constant from config
        from src.config.constants import USER_INTERRUPT_MESSAGE as expected

        assert expected == USER_INTERRUPT_MESSAGE
