"""Tests for src/web/routers/logs_api.py module.

This module tests the WebSocket-based log streaming functionality.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestGetLogFilePath:
    """Test _get_log_file_path function."""

    def test_get_log_file_path_returns_path(self) -> None:
        """Test that _get_log_file_path returns a Path object."""
        from src.web.routers.logs_api import _get_log_file_path

        result = _get_log_file_path()
        assert isinstance(result, Path)
        assert result.name == "app.log"


class TestReadFileContent:
    """Test _read_file_content function."""

    @pytest.mark.asyncio
    async def test_read_file_content(self, tmp_path: Path) -> None:
        """Test reading file content asynchronously."""
        from src.web.routers.logs_api import _read_file_content

        test_file = tmp_path / "test.log"
        test_content = "Line 1\nLine 2\nLine 3"
        test_file.write_text(test_content, encoding="utf-8")

        result = await _read_file_content(test_file)
        assert result == test_content

    @pytest.mark.asyncio
    async def test_read_file_content_with_unicode(self, tmp_path: Path) -> None:
        """Test reading file with unicode content."""
        from src.web.routers.logs_api import _read_file_content

        test_file = tmp_path / "test_unicode.log"
        test_content = "한글 테스트\n日本語テスト"
        test_file.write_text(test_content, encoding="utf-8")

        result = await _read_file_content(test_file)
        assert result == test_content


class TestReadFileRange:
    """Test _read_file_range function."""

    @pytest.mark.asyncio
    async def test_read_file_range(self, tmp_path: Path) -> None:
        """Test reading a range of bytes from file."""
        from src.web.routers.logs_api import _read_file_range

        test_file = tmp_path / "test_range.log"
        test_content = "0123456789ABCDEF"
        test_file.write_text(test_content, encoding="utf-8")

        result = await _read_file_range(test_file, 5, 10)
        assert result == "56789"

    @pytest.mark.asyncio
    async def test_read_file_range_start_zero(self, tmp_path: Path) -> None:
        """Test reading from start of file."""
        from src.web.routers.logs_api import _read_file_range

        test_file = tmp_path / "test_range2.log"
        test_content = "Hello World"
        test_file.write_text(test_content, encoding="utf-8")

        result = await _read_file_range(test_file, 0, 5)
        assert result == "Hello"


class TestGetFileSize:
    """Test _get_file_size function."""

    @pytest.mark.asyncio
    async def test_get_file_size(self, tmp_path: Path) -> None:
        """Test getting file size asynchronously."""
        from src.web.routers.logs_api import _get_file_size

        test_file = tmp_path / "test_size.log"
        test_content = "1234567890"
        test_file.write_text(test_content, encoding="utf-8")

        result = await _get_file_size(test_file)
        assert result == 10


class TestTailLogFile:
    """Test _tail_log_file function."""

    @pytest.mark.asyncio
    async def test_tail_log_file_not_exists(self) -> None:
        """Test tail_log_file when file doesn't exist."""
        from src.web.routers.logs_api import _tail_log_file

        mock_websocket = AsyncMock()
        non_existent_path = Path("/nonexistent/path/to/log.log")

        await _tail_log_file(mock_websocket, non_existent_path)

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert "Log file not found" in call_args["message"]

    @pytest.mark.asyncio
    async def test_tail_log_file_sends_initial_content(self, tmp_path: Path) -> None:
        """Test that initial content is sent to websocket."""
        from src.web.routers.logs_api import _tail_log_file

        test_file = tmp_path / "test.log"
        test_content = "\n".join([f"Line {i}" for i in range(10)])
        test_file.write_text(test_content, encoding="utf-8")

        mock_websocket = AsyncMock()

        # Create a task that will be cancelled after initial send
        async def run_with_timeout() -> None:
            task = asyncio.create_task(_tail_log_file(mock_websocket, test_file))
            await asyncio.sleep(0.1)  # Allow initial content to be sent
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_with_timeout()

        # Check initial content was sent
        assert mock_websocket.send_json.called
        first_call = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "initial"
        assert "lines" in first_call
        assert "total_lines" in first_call

    @pytest.mark.asyncio
    async def test_tail_log_file_buffer_size_limit(self, tmp_path: Path) -> None:
        """Test that buffer size limits the initial lines sent."""
        from src.web.routers.logs_api import _tail_log_file

        test_file = tmp_path / "test_large.log"
        # Create file with more lines than buffer
        test_content = "\n".join([f"Line {i}" for i in range(2000)])
        test_file.write_text(test_content, encoding="utf-8")

        mock_websocket = AsyncMock()

        async def run_with_timeout() -> None:
            task = asyncio.create_task(
                _tail_log_file(mock_websocket, test_file, buffer_size=100)
            )
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_with_timeout()

        first_call = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "initial"
        assert len(first_call["lines"]) == 100  # Buffer size limit
        assert first_call["total_lines"] == 2000

    @pytest.mark.asyncio
    async def test_tail_log_file_exception_handling(self, tmp_path: Path) -> None:
        """Test that exceptions during file read are handled."""
        from src.web.routers.logs_api import _tail_log_file

        test_file = tmp_path / "test_error.log"
        test_file.write_text("Test content", encoding="utf-8")

        mock_websocket = AsyncMock()

        with patch(
            "src.web.routers.logs_api._read_file_content",
            side_effect=PermissionError("Access denied"),
        ):
            await _tail_log_file(mock_websocket, test_file)

        error_call = mock_websocket.send_json.call_args[0][0]
        assert error_call["type"] == "error"

    @pytest.mark.asyncio
    async def test_tail_log_file_detects_new_content(self, tmp_path: Path) -> None:
        """Test that new content is detected and sent."""
        from src.web.routers.logs_api import _tail_log_file

        test_file = tmp_path / "test_update.log"
        test_file.write_text("Initial\n", encoding="utf-8")

        mock_websocket = AsyncMock()
        call_count = 0

        async def controlled_test() -> None:
            nonlocal call_count
            task = asyncio.create_task(_tail_log_file(mock_websocket, test_file))

            # Wait for initial content
            await asyncio.sleep(0.2)

            # Append new content
            with open(test_file, "a", encoding="utf-8") as f:
                f.write("New line 1\nNew line 2\n")

            # Wait for update to be detected
            await asyncio.sleep(1.5)

            call_count = mock_websocket.send_json.call_count
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await controlled_test()

        # Should have at least 2 calls: initial + update
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_tail_log_file_file_truncation(self, tmp_path: Path) -> None:
        """Test handling of file truncation/rotation."""
        from src.web.routers.logs_api import _tail_log_file

        test_file = tmp_path / "test_truncate.log"
        test_file.write_text("Long initial content here\n" * 100, encoding="utf-8")

        mock_websocket = AsyncMock()

        async def truncation_test() -> None:
            task = asyncio.create_task(_tail_log_file(mock_websocket, test_file))
            await asyncio.sleep(0.2)

            # Truncate file
            test_file.write_text("New short content\n", encoding="utf-8")

            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await truncation_test()
        # Should not raise, truncation is handled


class TestWebsocketLogsEndpoint:
    """Test websocket_logs endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_logs_accepts_connection(self) -> None:
        """Test that websocket connection is accepted."""
        from src.web.routers.logs_api import websocket_logs

        mock_websocket = AsyncMock()

        with (
            patch(
                "src.web.routers.logs_api._get_log_file_path",
                return_value=Path("/nonexistent/app.log"),
            ),
            patch(
                "src.web.routers.logs_api._tail_log_file", new_callable=AsyncMock
            ) as mock_tail,
        ):
            await websocket_logs(mock_websocket)

        mock_websocket.accept.assert_called_once()
        mock_websocket.close.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_logs_handles_disconnect(self) -> None:
        """Test handling of WebSocket disconnect."""
        from fastapi import WebSocketDisconnect

        from src.web.routers.logs_api import websocket_logs

        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        with (
            patch(
                "src.web.routers.logs_api._get_log_file_path",
                return_value=Path("/tmp/app.log"),
            ),
            patch(
                "src.web.routers.logs_api._tail_log_file",
                side_effect=WebSocketDisconnect(),
            ),
        ):
            await websocket_logs(mock_websocket)

        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_logs_handles_exception(self) -> None:
        """Test handling of unexpected exceptions."""
        from src.web.routers.logs_api import websocket_logs

        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()

        with (
            patch(
                "src.web.routers.logs_api._get_log_file_path",
                return_value=Path("/tmp/app.log"),
            ),
            patch(
                "src.web.routers.logs_api._tail_log_file",
                side_effect=RuntimeError("Unexpected error"),
            ),
        ):
            # Should not raise
            await websocket_logs(mock_websocket)


class TestModuleExports:
    """Test module exports."""

    def test_router_export(self) -> None:
        """Test router is exported."""
        from src.web.routers.logs_api import router

        assert router is not None
        assert router.prefix == "/api/ws"

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from src.web.routers import logs_api

        assert hasattr(logs_api, "__all__")
        assert "router" in logs_api.__all__
