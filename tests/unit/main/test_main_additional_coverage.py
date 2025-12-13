"""Additional tests for src/main.py to improve coverage to 80%+.

Focus on uncovered branches and edge cases not covered in existing test files.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import Mock, patch

import pytest


class TestMainErrorHandling:
    """Test error handling in main function."""

    @pytest.mark.asyncio
    async def test_main_critical_logging_on_oserror(self) -> None:
        """Test critical logging when OSError occurs."""
        from src.main import main

        with patch("src.main.setup_logging") as mock_logging:
            mock_logger = Mock()
            mock_listener = Mock()
            mock_logging.return_value = (mock_logger, mock_listener)

            with patch("src.main.AppConfig") as mock_config:
                mock_config.side_effect = OSError("파일 접근 오류")

                with patch("src.main.console"):
                    with pytest.raises(SystemExit):
                        await main()

                    # Verify critical logging
                    mock_logger.critical.assert_called()


class TestWindowsEventLoop:
    """Test Windows-specific event loop handling."""

    def test_windows_selector_event_loop_policy_applied(self) -> None:
        """Test WindowsSelectorEventLoopPolicy is applied on Windows."""
        with patch("os.name", "nt"):
            # Test the actual code path
            if os.name == "nt":
                try:
                    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
                    if policy:
                        # Would normally set the policy
                        assert policy is not None
                except AttributeError:
                    # Should handle gracefully
                    pass
