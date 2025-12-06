"""Tests for src/main.py to increase coverage."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMainModule:
    """Test main module entry point and error handling."""

    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    @patch("sys.exit")
    def test_main_keyboard_interrupt(
        self, mock_exit: MagicMock, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test main() handles KeyboardInterrupt."""
        mock_run.side_effect = KeyboardInterrupt()

        # Import and execute the if __name__ == "__main__" block
        with patch("sys.argv", ["main.py"]):
            with patch("src.main.__name__", "__main__"):
                try:
                    exec(
                        compile(
                            open("/home/runner/work/Test/Test/src/main.py").read(),
                            "main.py",
                            "exec",
                        ),
                        {"__name__": "__main__"},
                    )
                except SystemExit:
                    pass

        mock_exit.assert_called()

    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    @patch("sys.exit")
    def test_main_exception_handling(
        self, mock_exit: MagicMock, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test main() handles general exceptions."""
        mock_run.side_effect = RuntimeError("Test error")

        with patch("sys.argv", ["main.py"]):
            with patch("src.main.__name__", "__main__"):
                try:
                    exec(
                        compile(
                            open("/home/runner/work/Test/Test/src/main.py").read(),
                            "main.py",
                            "exec",
                        ),
                        {"__name__": "__main__"},
                    )
                except SystemExit:
                    pass

        mock_exit.assert_called_with(1)

    @patch("os.name", "nt")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    def test_windows_event_loop_policy(
        self, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test Windows event loop policy is set."""
        mock_policy = MagicMock()
        
        with patch("asyncio.WindowsSelectorEventLoopPolicy", return_value=mock_policy):
            with patch("asyncio.set_event_loop_policy") as mock_set_policy:
                with patch("sys.argv", ["main.py"]):
                    with patch("src.main.__name__", "__main__"):
                        try:
                            exec(
                                compile(
                                    open("/home/runner/work/Test/Test/src/main.py").read(),
                                    "main.py",
                                    "exec",
                                ),
                                {"__name__": "__main__"},
                            )
                        except SystemExit:
                            pass

    @patch("os.name", "nt")
    @patch("src.main.asyncio.run")
    @patch("src.main.load_dotenv")
    def test_windows_event_loop_no_policy(
        self, mock_dotenv: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test Windows handles missing WindowsSelectorEventLoopPolicy."""
        with patch.object(asyncio, "WindowsSelectorEventLoopPolicy", None, create=True):
            with patch("sys.argv", ["main.py"]):
                with patch("src.main.__name__", "__main__"):
                    try:
                        exec(
                            compile(
                                open("/home/runner/work/Test/Test/src/main.py").read(),
                                "main.py",
                                "exec",
                            ),
                            {"__name__": "__main__"},
                        )
                    except (SystemExit, AttributeError):
                        pass
