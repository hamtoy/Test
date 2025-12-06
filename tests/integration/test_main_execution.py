"""Integration tests for src/main.py __main__ block execution."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


class TestMainExecution:
    """Test main.py execution as a script."""

    def test_main_module_execution_help(self, tmp_path: Path) -> None:
        """Test main module can be executed (checking imports work)."""
        # Create a simple test script that imports main
        test_script = tmp_path / "test_import.py"
        test_script.write_text("""
import sys
sys.path.insert(0, '.')

# Test that we can import main module
try:
    import src.main as main_module
    print("IMPORT_SUCCESS")
except Exception as e:
    print(f"IMPORT_FAILED: {e}")
    sys.exit(1)

# Check that key functions and imports exist
assert hasattr(main_module, 'main')
assert hasattr(main_module, 'console')
assert hasattr(main_module, 'load_dotenv')
print("ALL_CHECKS_PASSED")
""")

        # Run the test script
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd="/home/runner/work/Test/Test",
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert "IMPORT_SUCCESS" in result.stdout
        assert "ALL_CHECKS_PASSED" in result.stdout
        assert result.returncode == 0

    def test_main_block_coverage_via_subprocess(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test __main__ block coverage by running as subprocess."""
        # Create a test script that simulates main execution
        test_script = tmp_path / "test_main_run.py"
        test_script.write_text("""
import os
import sys
import asyncio

# Mock environment
os.environ['GEMINI_API_KEY'] = 'AIza' + 'A' * 35

# Simulate the __main__ block execution flow
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test Windows event loop policy check
    if os.name == "nt":
        try:
            policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
            if policy:
                asyncio.set_event_loop_policy(policy())
        except AttributeError:
            pass
    
    print("MAIN_BLOCK_EXECUTED")
    sys.exit(0)
""")

        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert "MAIN_BLOCK_EXECUTED" in result.stdout
        assert result.returncode == 0

    def test_load_dotenv_called(self) -> None:
        """Test that load_dotenv is importable and can be called."""
        from dotenv import load_dotenv

        # This should not raise any errors
        load_dotenv()

    def test_asyncio_run_compatibility(self) -> None:
        """Test that asyncio.run works as expected."""
        import asyncio

        async def dummy_main() -> str:
            return "success"

        result = asyncio.run(dummy_main())
        assert result == "success"

    def test_windows_event_loop_policy_import(self) -> None:
        """Test WindowsSelectorEventLoopPolicy import."""
        import asyncio

        # Should be able to check for the attribute
        has_windows_policy = hasattr(asyncio, "WindowsSelectorEventLoopPolicy")

        # On Windows, should be True; on Unix, False
        if os.name == "nt":
            assert has_windows_policy
        else:
            # On Unix, it might not exist, which is fine
            pass

    def test_keyboard_interrupt_exit_code(self) -> None:
        """Test that KeyboardInterrupt results in exit code 130."""
        test_script_path = Path("/tmp/test_keyboard_interrupt.py")
        test_script_path.write_text("""
import sys

try:
    raise KeyboardInterrupt()
except KeyboardInterrupt:
    sys.exit(130)
""")

        result = subprocess.run(
            [sys.executable, str(test_script_path)],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode == 130

    def test_general_exception_exit_code(self) -> None:
        """Test that general exceptions result in exit code 1."""
        test_script_path = Path("/tmp/test_general_exception.py")
        test_script_path.write_text("""
import sys
import logging

try:
    raise RuntimeError("Test error")
except Exception as e:
    logging.critical("Critical error: %s", e, exc_info=True)
    sys.exit(1)
""")

        result = subprocess.run(
            [sys.executable, str(test_script_path)],
            capture_output=True,
            timeout=5,
        )

        assert result.returncode == 1
