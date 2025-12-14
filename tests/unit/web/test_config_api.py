"""Tests for src/web/routers/config_api.py module.

This module tests the configuration API endpoints for reading and updating settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


class TestConfigResponse:
    """Test ConfigResponse Pydantic model."""

    def test_config_response_defaults(self) -> None:
        """Test ConfigResponse with default values."""
        from src.web.routers.config_api import ConfigResponse

        config = ConfigResponse()

        assert config.llm_model == ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.log_level == "INFO"
        assert config.output_dir == "output"
        assert config.enable_cache is True
        assert config.cache_ttl == 3600

    def test_config_response_custom_values(self) -> None:
        """Test ConfigResponse with custom values."""
        from src.web.routers.config_api import ConfigResponse

        config = ConfigResponse(
            llm_model="gemini-pro",
            temperature=0.9,
            max_tokens=8192,
            log_level="DEBUG",
            output_dir="custom_output",
            enable_cache=False,
            cache_ttl=7200,
        )

        assert config.llm_model == "gemini-pro"
        assert config.temperature == 0.9
        assert config.max_tokens == 8192
        assert config.log_level == "DEBUG"
        assert config.output_dir == "custom_output"
        assert config.enable_cache is False
        assert config.cache_ttl == 7200

    def test_config_response_temperature_bounds(self) -> None:
        """Test temperature field bounds validation."""
        from src.web.routers.config_api import ConfigResponse

        # Valid boundaries
        ConfigResponse(temperature=0.0)
        ConfigResponse(temperature=2.0)

        # Invalid values
        with pytest.raises(ValidationError):
            ConfigResponse(temperature=-0.1)

        with pytest.raises(ValidationError):
            ConfigResponse(temperature=2.1)

    def test_config_response_max_tokens_minimum(self) -> None:
        """Test max_tokens minimum validation."""
        from src.web.routers.config_api import ConfigResponse

        ConfigResponse(max_tokens=1)

        with pytest.raises(ValidationError):
            ConfigResponse(max_tokens=0)

    def test_config_response_cache_ttl_minimum(self) -> None:
        """Test cache_ttl minimum validation."""
        from src.web.routers.config_api import ConfigResponse

        ConfigResponse(cache_ttl=0)

        with pytest.raises(ValidationError):
            ConfigResponse(cache_ttl=-1)


class TestConfigUpdateRequest:
    """Test ConfigUpdateRequest Pydantic model."""

    def test_config_update_request_all_none(self) -> None:
        """Test ConfigUpdateRequest with all None values."""
        from src.web.routers.config_api import ConfigUpdateRequest

        request = ConfigUpdateRequest()

        assert request.llm_model is None
        assert request.temperature is None
        assert request.max_tokens is None
        assert request.log_level is None
        assert request.output_dir is None
        assert request.enable_cache is None
        assert request.cache_ttl is None

    def test_config_update_request_partial(self) -> None:
        """Test ConfigUpdateRequest with partial values."""
        from src.web.routers.config_api import ConfigUpdateRequest

        request = ConfigUpdateRequest(
            temperature=0.5,
            enable_cache=True,
        )

        assert request.temperature == 0.5
        assert request.enable_cache is True
        assert request.llm_model is None

    def test_config_update_request_log_level_validation(self) -> None:
        """Test log_level field validation."""
        from src.web.routers.config_api import ConfigUpdateRequest

        # Valid levels get uppercased
        request = ConfigUpdateRequest(log_level="debug")
        assert request.log_level == "DEBUG"

        request = ConfigUpdateRequest(log_level="INFO")
        assert request.log_level == "INFO"

        request = ConfigUpdateRequest(log_level="warning")
        assert request.log_level == "WARNING"

        request = ConfigUpdateRequest(log_level="Error")
        assert request.log_level == "ERROR"

        request = ConfigUpdateRequest(log_level="critical")
        assert request.log_level == "CRITICAL"

        # Invalid level
        with pytest.raises(ValidationError):
            ConfigUpdateRequest(log_level="INVALID")

    def test_config_update_request_log_level_none(self) -> None:
        """Test that log_level None is allowed."""
        from src.web.routers.config_api import ConfigUpdateRequest

        request = ConfigUpdateRequest(log_level=None)
        assert request.log_level is None


class TestGetEnvFilePath:
    """Test _get_env_file_path function."""

    def test_get_env_file_path_returns_path(self) -> None:
        """Test that _get_env_file_path returns correct path."""
        from src.web.routers.config_api import _get_env_file_path

        result = _get_env_file_path()

        assert isinstance(result, Path)
        assert result.name == ".env"


class TestReadEnvFile:
    """Test _read_env_file function."""

    def test_read_env_file_not_exists(self, tmp_path: Path) -> None:
        """Test reading non-existent .env file."""
        from src.web.routers.config_api import _read_env_file

        with patch(
            "src.web.routers.config_api._get_env_file_path",
            return_value=tmp_path / ".env",
        ):
            result = _read_env_file()

        assert result == {}

    def test_read_env_file_parses_correctly(self, tmp_path: Path) -> None:
        """Test parsing .env file content."""
        from src.web.routers.config_api import _read_env_file

        env_file = tmp_path / ".env"
        env_file.write_text(
            """
KEY1=value1
KEY2=value2
# Comment line
KEY3='quoted value'
KEY4="double quoted"
EMPTY=
""",
            encoding="utf-8",
        )

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            result = _read_env_file()

        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
        assert result["KEY3"] == "quoted value"
        assert result["KEY4"] == "double quoted"
        assert result["EMPTY"] == ""

    def test_read_env_file_ignores_comments(self, tmp_path: Path) -> None:
        """Test that comments are ignored."""
        from src.web.routers.config_api import _read_env_file

        env_file = tmp_path / ".env"
        env_file.write_text(
            """
# This is a comment
KEY=value
# Another comment
""",
            encoding="utf-8",
        )

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            result = _read_env_file()

        assert len(result) == 1
        assert result["KEY"] == "value"

    def test_read_env_file_ignores_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are ignored."""
        from src.web.routers.config_api import _read_env_file

        env_file = tmp_path / ".env"
        env_file.write_text(
            """
KEY1=value1

KEY2=value2

""",
            encoding="utf-8",
        )

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            result = _read_env_file()

        assert len(result) == 2


class TestProcessExistingLine:
    """Test _process_existing_line function."""

    def test_process_existing_line_comment(self) -> None:
        """Test processing comment line."""
        from src.web.routers.config_api import _process_existing_line

        updates: dict[str, str] = {}
        updated_keys: set[str] = set()

        result = _process_existing_line("# Comment", updates, updated_keys)

        assert result == "# Comment"
        assert len(updated_keys) == 0

    def test_process_existing_line_empty(self) -> None:
        """Test processing empty line."""
        from src.web.routers.config_api import _process_existing_line

        updates: dict[str, str] = {}
        updated_keys: set[str] = set()

        result = _process_existing_line("", updates, updated_keys)

        assert result == ""

    def test_process_existing_line_no_equals(self) -> None:
        """Test processing line without equals sign."""
        from src.web.routers.config_api import _process_existing_line

        updates: dict[str, str] = {}
        updated_keys: set[str] = set()

        result = _process_existing_line("invalid line", updates, updated_keys)

        assert result == "invalid line"

    def test_process_existing_line_update(self) -> None:
        """Test updating a key."""
        from src.web.routers.config_api import _process_existing_line

        updates = {"KEY": "new_value"}
        updated_keys: set[str] = set()

        result = _process_existing_line("KEY=old_value", updates, updated_keys)

        assert result == "KEY=new_value"
        assert "KEY" in updated_keys

    def test_process_existing_line_no_update(self) -> None:
        """Test line that doesn't need update."""
        from src.web.routers.config_api import _process_existing_line

        updates = {"OTHER": "value"}
        updated_keys: set[str] = set()

        result = _process_existing_line("KEY=value", updates, updated_keys)

        assert result == "KEY=value"
        assert "KEY" not in updated_keys


class TestWriteEnvFile:
    """Test _write_env_file function."""

    def test_write_env_file_creates_new(self, tmp_path: Path) -> None:
        """Test writing to new .env file."""
        from src.web.routers.config_api import _write_env_file

        env_file = tmp_path / ".env"

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            _write_env_file({"KEY1": "value1", "KEY2": "value2"})

        content = env_file.read_text(encoding="utf-8")
        assert "KEY1=value1" in content
        assert "KEY2=value2" in content

    def test_write_env_file_updates_existing(self, tmp_path: Path) -> None:
        """Test updating existing .env file."""
        from src.web.routers.config_api import _write_env_file

        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=old\nKEY2=keep\n", encoding="utf-8")

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            _write_env_file({"KEY1": "new"})

        content = env_file.read_text(encoding="utf-8")
        assert "KEY1=new" in content
        assert "KEY2=keep" in content

    def test_write_env_file_adds_new_keys(self, tmp_path: Path) -> None:
        """Test adding new keys to existing .env file."""
        from src.web.routers.config_api import _write_env_file

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value\n", encoding="utf-8")

        with patch(
            "src.web.routers.config_api._get_env_file_path", return_value=env_file
        ):
            _write_env_file({"NEW_KEY": "new_value"})

        content = env_file.read_text(encoding="utf-8")
        assert "EXISTING=value" in content
        assert "NEW_KEY=new_value" in content


class TestConfigEnvMap:
    """Test CONFIG_ENV_MAP constant."""

    def test_config_env_map_contains_all_fields(self) -> None:
        """Test that CONFIG_ENV_MAP contains all config fields."""
        from src.web.routers.config_api import CONFIG_ENV_MAP

        expected_fields = [
            "llm_model",
            "temperature",
            "max_tokens",
            "log_level",
            "output_dir",
            "enable_cache",
            "cache_ttl",
        ]

        for field in expected_fields:
            assert field in CONFIG_ENV_MAP


class TestGetConfigEndpoint:
    """Test get_config API endpoint."""

    @pytest.mark.asyncio
    async def test_get_config_returns_defaults(self) -> None:
        """Test get_config returns default values."""
        from src.web.routers.config_api import get_config

        with patch("src.web.routers.config_api._read_env_file", return_value={}):
            with patch.dict(os.environ, {}, clear=False):
                result = await get_config()

        assert result.temperature == 0.7
        assert result.max_tokens == 4096
        assert result.log_level == "INFO"

    @pytest.mark.asyncio
    async def test_get_config_reads_env_file(self) -> None:
        """Test get_config reads from .env file."""
        from src.web.routers.config_api import get_config

        mock_env = {
            "LLM_MODEL": "gemini-flash",
            "LLM_TEMPERATURE": "0.5",
            "LLM_MAX_TOKENS": "2048",
        }

        with patch("src.web.routers.config_api._read_env_file", return_value=mock_env):
            result = await get_config()

        assert result.llm_model == "gemini-flash"
        assert result.temperature == 0.5
        assert result.max_tokens == 2048

    @pytest.mark.asyncio
    async def test_get_config_merges_env_variables(self) -> None:
        """Test get_config merges environment variables with .env file."""
        from src.web.routers.config_api import get_config

        env_file_data = {"LLM_MODEL": "from-file"}

        with (
            patch(
                "src.web.routers.config_api._read_env_file", return_value=env_file_data
            ),
            patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False),
        ):
            result = await get_config()

        assert result.llm_model == "from-file"
        assert result.log_level == "DEBUG"

    @pytest.mark.asyncio
    async def test_get_config_env_file_overrides_os_env(self) -> None:
        """Test that .env file values override os.environ."""
        from src.web.routers.config_api import get_config

        env_file_data = {"LOG_LEVEL": "ERROR"}

        with (
            patch(
                "src.web.routers.config_api._read_env_file", return_value=env_file_data
            ),
            patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False),
        ):
            result = await get_config()

        assert result.log_level == "ERROR"

    @pytest.mark.asyncio
    async def test_get_config_enable_cache_parsing(self) -> None:
        """Test enable_cache boolean parsing."""
        from src.web.routers.config_api import get_config

        # Test "true"
        with patch(
            "src.web.routers.config_api._read_env_file",
            return_value={"ENABLE_CACHE": "true"},
        ):
            result = await get_config()
            assert result.enable_cache is True

        # Test "false"
        with patch(
            "src.web.routers.config_api._read_env_file",
            return_value={"ENABLE_CACHE": "false"},
        ):
            result = await get_config()
            assert result.enable_cache is False

        # Test "TRUE" (uppercase)
        with patch(
            "src.web.routers.config_api._read_env_file",
            return_value={"ENABLE_CACHE": "TRUE"},
        ):
            result = await get_config()
            assert result.enable_cache is True

    @pytest.mark.asyncio
    async def test_get_config_fallback_to_gemini_model(self) -> None:
        """Test fallback to GEMINI_MODEL if LLM_MODEL not set."""
        from src.web.routers.config_api import get_config

        with patch(
            "src.web.routers.config_api._read_env_file",
            return_value={"GEMINI_MODEL": "gemini-pro"},
        ):
            result = await get_config()

        assert result.llm_model == "gemini-pro"


class TestUpdateConfigEndpoint:
    """Test update_config API endpoint."""

    @pytest.mark.asyncio
    async def test_update_config_updates_values(self) -> None:
        """Test update_config updates .env file."""
        from src.web.routers.config_api import ConfigUpdateRequest, update_config

        request = ConfigUpdateRequest(temperature=0.8, max_tokens=2048)

        with patch("src.web.routers.config_api._write_env_file") as mock_write:
            with patch(
                "src.web.routers.config_api._read_env_file",
                return_value={"LLM_TEMPERATURE": "0.8", "LLM_MAX_TOKENS": "2048"},
            ):
                result = await update_config(request)

        mock_write.assert_called_once()
        call_args = mock_write.call_args[0][0]
        assert call_args["LLM_TEMPERATURE"] == "0.8"
        assert call_args["LLM_MAX_TOKENS"] == "2048"

    @pytest.mark.asyncio
    async def test_update_config_no_fields_raises_error(self) -> None:
        """Test update_config raises error when no fields to update."""
        from src.web.routers.config_api import ConfigUpdateRequest, update_config

        request = ConfigUpdateRequest()  # All None

        with pytest.raises(HTTPException) as exc_info:
            await update_config(request)

        assert exc_info.value.status_code == 400
        assert "No valid fields" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_config_boolean_conversion(self) -> None:
        """Test that boolean values are converted to strings correctly."""
        from src.web.routers.config_api import ConfigUpdateRequest, update_config

        request = ConfigUpdateRequest(enable_cache=True)

        with patch("src.web.routers.config_api._write_env_file") as mock_write:
            with patch(
                "src.web.routers.config_api._read_env_file",
                return_value={"ENABLE_CACHE": "true"},
            ):
                await update_config(request)

        call_args = mock_write.call_args[0][0]
        assert call_args["ENABLE_CACHE"] == "true"

        # Test False
        request = ConfigUpdateRequest(enable_cache=False)

        with patch("src.web.routers.config_api._write_env_file") as mock_write:
            with patch(
                "src.web.routers.config_api._read_env_file",
                return_value={"ENABLE_CACHE": "false"},
            ):
                await update_config(request)

        call_args = mock_write.call_args[0][0]
        assert call_args["ENABLE_CACHE"] == "false"

    @pytest.mark.asyncio
    async def test_update_config_write_error(self) -> None:
        """Test update_config handles write errors."""
        from src.web.routers.config_api import ConfigUpdateRequest, update_config

        request = ConfigUpdateRequest(temperature=0.5)

        with (
            patch(
                "src.web.routers.config_api._write_env_file",
                side_effect=PermissionError("Access denied"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_config(request)

        assert exc_info.value.status_code == 500
        assert "Failed to update config" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_config_returns_updated_config(self) -> None:
        """Test update_config returns the updated configuration."""
        from src.web.routers.config_api import ConfigUpdateRequest, update_config

        request = ConfigUpdateRequest(log_level="DEBUG")

        with (
            patch("src.web.routers.config_api._write_env_file"),
            patch(
                "src.web.routers.config_api._read_env_file",
                return_value={"LOG_LEVEL": "DEBUG"},
            ),
        ):
            result = await update_config(request)

        assert result.log_level == "DEBUG"


class TestRouter:
    """Test router configuration."""

    def test_router_prefix(self) -> None:
        """Test router has correct prefix."""
        from src.web.routers.config_api import router

        assert router.prefix == "/api/config"

    def test_router_tags(self) -> None:
        """Test router has correct tags."""
        from src.web.routers.config_api import router

        assert "config" in router.tags


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from src.web.routers import config_api

        assert hasattr(config_api, "__all__")
        assert "router" in config_api.__all__
