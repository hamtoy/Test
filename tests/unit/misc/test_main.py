"""Tests for main.py entry point."""
# mypy: ignore-errors

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.main import main


class TestMainFunction:
    """Tests for main() function."""

    @pytest.mark.asyncio
    @patch("src.main.setup_logging")
    @patch("src.main.AppConfig")
    @patch("src.main.genai.configure")
    @patch("jinja2.Environment")
    @patch("jinja2.FileSystemLoader")
    @patch("src.main.GeminiAgent")
    @patch("src.main.interactive_main")
    async def test_main_success(
        self,
        mock_interactive,
        mock_agent_class,
        mock_loader_class,
        mock_env_class,
        mock_genai_configure,
        mock_config_class,
        mock_setup_logging,
    ):
        """Test successful main() execution."""
        # Setup mocks
        mock_logger = Mock()
        mock_log_listener = Mock()
        mock_setup_logging.return_value = (mock_logger, mock_log_listener)

        mock_config = Mock()
        mock_config.api_key = "test-api-key"
        mock_config.template_dir = Mock()
        mock_config.template_dir.exists.return_value = True
        mock_config.max_concurrency = 5
        mock_config_class.return_value = mock_config

        mock_env = Mock()
        mock_env_class.return_value = mock_env

        mock_agent = Mock()
        mock_agent_class.return_value = mock_agent

        mock_interactive.return_value = AsyncMock()

        # Execute
        await main()

        # Verify
        mock_setup_logging.assert_called_once()
        mock_config_class.assert_called_once()
        mock_genai_configure.assert_called_once_with(api_key="test-api-key")
        mock_env_class.assert_called_once()
        mock_agent_class.assert_called_once()
        mock_interactive.assert_called_once()
        mock_log_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.setup_logging")
    @patch("src.main.AppConfig")
    @patch("src.main.console")
    async def test_main_config_file_not_found(
        self, mock_console, mock_config_class, mock_setup_logging
    ):
        """Test main() with missing template directory."""
        # Setup mocks
        mock_logger = Mock()
        mock_log_listener = Mock()
        mock_setup_logging.return_value = (mock_logger, mock_log_listener)

        mock_config = Mock()
        mock_config.api_key = "test-api-key"
        mock_config.template_dir = Mock()
        mock_config.template_dir.exists.return_value = False
        mock_config.max_concurrency = 5
        mock_config_class.return_value = mock_config

        # Execute and expect sys.exit
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1
        mock_log_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.setup_logging")
    @patch("src.main.AppConfig")
    async def test_main_value_error(self, mock_config_class, mock_setup_logging):
        """Test main() with ValueError during initialization."""
        # Setup mocks
        mock_logger = Mock()
        mock_log_listener = Mock()
        mock_setup_logging.return_value = (mock_logger, mock_log_listener)

        mock_config_class.side_effect = ValueError("Invalid configuration")

        # Execute and expect sys.exit
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1
        mock_log_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.setup_logging")
    @patch("src.main.AppConfig")
    async def test_main_os_error(self, mock_config_class, mock_setup_logging):
        """Test main() with OSError during initialization."""
        # Setup mocks
        mock_logger = Mock()
        mock_log_listener = Mock()
        mock_setup_logging.return_value = (mock_logger, mock_log_listener)

        mock_config_class.side_effect = OSError("File operation failed")

        # Execute and expect sys.exit
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1
        mock_log_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.setup_logging")
    @patch("src.main.AppConfig")
    @patch("src.main.genai.configure")
    @patch("jinja2.Environment")
    @patch("jinja2.FileSystemLoader")
    @patch("src.main.GeminiAgent")
    @patch("src.main.interactive_main")
    async def test_main_jinja_env_setup(
        self,
        mock_interactive,
        mock_agent_class,
        mock_loader_class,
        mock_env_class,
        mock_genai_configure,
        mock_config_class,
        mock_setup_logging,
    ):
        """Test that Jinja2 environment is set up correctly."""
        # Setup mocks
        mock_logger = Mock()
        mock_log_listener = Mock()
        mock_setup_logging.return_value = (mock_logger, mock_log_listener)

        mock_config = Mock()
        mock_config.api_key = "test-api-key"
        mock_config.template_dir = Mock()
        mock_config.template_dir.exists.return_value = True
        mock_config.max_concurrency = 5
        mock_config_class.return_value = mock_config

        mock_env = Mock()
        mock_env_class.return_value = mock_env

        mock_interactive.return_value = AsyncMock()

        # Execute
        await main()

        # Verify Jinja2 environment was created with correct parameters
        mock_env_class.assert_called_once()
        call_kwargs = mock_env_class.call_args[1]
        assert call_kwargs["autoescape"] is True


class TestMainImports:
    """Tests to ensure all imports are available."""

    def test_imports_available(self):
        """Test that all expected imports are available."""
        from src.main import (
            analyze_cache_stats,
            execute_workflow,
            load_input_data,
            parse_args,
            print_cache_report,
            render_cost_panel,
            write_cache_stats,
        )

        # These imports should be available (marked with noqa: F401)
        assert analyze_cache_stats is not None
        assert print_cache_report is not None
        assert parse_args is not None
        assert write_cache_stats is not None
        assert load_input_data is not None
        assert render_cost_panel is not None
        assert execute_workflow is not None
