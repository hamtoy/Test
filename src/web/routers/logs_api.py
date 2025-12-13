# mypy: allow-untyped-decorators
"""Logs streaming API via WebSocket - Optimized with aiofiles."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ws", tags=["logs"])


def _get_log_file_path() -> Path:
    """Get the path to the application log file."""
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "app.log"


async def _read_file_content(path: Path) -> str:
    """Read file content asynchronously using aiofiles."""
    async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
        return await f.read()


async def _read_file_range(path: Path, start: int, end: int) -> str:
    """Read a range of bytes from file asynchronously."""
    async with aiofiles.open(path, mode="r", encoding="utf-8", errors="replace") as f:
        await f.seek(start)
        return await f.read(end - start)


async def _get_file_size(path: Path) -> int:
    """Get file size asynchronously."""
    stat = await aiofiles.os.stat(path)
    return stat.st_size


async def _tail_log_file(
    websocket: WebSocket,
    log_path: Path,
    buffer_size: int = 1000,
) -> None:
    """Stream log file content to WebSocket client.

    Args:
        websocket: WebSocket connection
        log_path: Path to log file
        buffer_size: Maximum lines to keep in buffer
    """
    if not log_path.exists():
        await websocket.send_json({"type": "error", "message": "Log file not found"})
        return

    # Send initial content (last N lines)
    try:
        content = await _read_file_content(log_path)
        lines = content.splitlines()
        initial_lines = lines[-buffer_size:] if len(lines) > buffer_size else lines

        await websocket.send_json(
            {
                "type": "initial",
                "lines": initial_lines,
                "total_lines": len(lines),
            }
        )
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        return

    # Track file position for new content
    last_size = await _get_file_size(log_path)

    # Stream new content
    try:
        while True:
            await asyncio.sleep(1)  # Poll every second

            current_size = await _get_file_size(log_path)
            if current_size > last_size:
                # Read new content using aiofiles
                new_content = await _read_file_range(log_path, last_size, current_size)
                if new_content:
                    new_lines = new_content.splitlines()
                    await websocket.send_json(
                        {
                            "type": "update",
                            "lines": new_lines,
                        }
                    )
                last_size = current_size
            elif current_size < last_size:
                # File was truncated or rotated
                last_size = 0
    except WebSocketDisconnect:
        pass  # Normal disconnection
    except Exception as e:
        logger.warning("Log streaming error: %s", e)


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time log streaming."""
    await websocket.accept()
    logger.info("Log streaming WebSocket connected")

    try:
        log_path = _get_log_file_path()
        await _tail_log_file(websocket, log_path)
    except WebSocketDisconnect:
        logger.info("Log streaming WebSocket disconnected")
    except Exception as e:
        logger.error("Log streaming error: %s", e)
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


__all__ = ["router"]
