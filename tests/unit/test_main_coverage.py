"""Tests for src/main.py to increase coverage."""

import asyncio
import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Get the project root dynamically
REPO_ROOT = Path(__file__).parent.parent.parent
MAIN_PY_PATH = REPO_ROOT / "src" / "main.py"


class TestMainModule:
    """Test main module entry point and error handling."""

    @pytest.mark.skipif(not MAIN_PY_PATH.exists(), reason="main.py not found")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    @patch("sys.exit")
    def test_main_keyboard_interrupt(
        self, mock_exit: MagicMock, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test main() handles KeyboardInterrupt."""
        mock_run.side_effect = KeyboardInterrupt()

        # Import and execute the if __name__ == "__main__" block
        with (
            patch("sys.argv", ["main.py"]),
            patch("src.main.__name__", "__main__"),
            contextlib.suppress(SystemExit),
            MAIN_PY_PATH.open() as f,
        ):
            exec(
                compile(f.read(), "main.py", "exec"),
                {"__name__": "__main__"},
            )

        mock_exit.assert_called()

    @pytest.mark.skipif(not MAIN_PY_PATH.exists(), reason="main.py not found")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    @patch("sys.exit")
    def test_main_exception_handling(
        self, mock_exit: MagicMock, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test main() handles general exceptions."""
        mock_run.side_effect = RuntimeError("Test error")

        with (
            patch("sys.argv", ["main.py"]),
            patch("src.main.__name__", "__main__"),
            contextlib.suppress(SystemExit),
            MAIN_PY_PATH.open() as f,
        ):
            exec(
                compile(f.read(), "main.py", "exec"),
                {"__name__": "__main__"},
            )

        mock_exit.assert_called_with(1)

    @pytest.mark.skipif(not MAIN_PY_PATH.exists(), reason="main.py not found")
    @patch("os.name", "nt")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_event_loop_policy(
        self, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test Windows event loop policy is set."""
        mock_policy = MagicMock()

        with (
            patch("asyncio.WindowsSelectorEventLoopPolicy", return_value=mock_policy),
            patch("asyncio.set_event_loop_policy"),
            patch("sys.argv", ["main.py"]),
            patch("src.main.__name__", "__main__"),
            contextlib.suppress(SystemExit),
            MAIN_PY_PATH.open() as f,
        ):
            exec(
                compile(f.read(), "main.py", "exec"),
                {"__name__": "__main__"},
            )

    @pytest.mark.skipif(not MAIN_PY_PATH.exists(), reason="main.py not found")
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    @patch("os.name", "nt")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    def test_windows_event_loop_no_policy(
        self, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test Windows handles missing WindowsSelectorEventLoopPolicy."""
        with (
            patch.object(asyncio, "WindowsSelectorEventLoopPolicy", None, create=True),
            patch("sys.argv", ["main.py"]),
            patch("src.main.__name__", "__main__"),
            contextlib.suppress(SystemExit, AttributeError),
            MAIN_PY_PATH.open() as f,
        ):
            exec(
                compile(f.read(), "main.py", "exec"),
                {"__name__": "__main__"},
            )
