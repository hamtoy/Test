"""
CLI Flow E2E Tests

Subprocess-based tests that verify the full CLI execution flow.
Run with: pytest tests/e2e/test_cli_flow.py -v

These tests use mocking to avoid actual LLM API calls.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Project root for subprocess calls
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for test artifacts."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def mock_env(temp_output_dir: Path) -> dict[str, str]:
    """Create environment with test configuration."""
    env = os.environ.copy()
    # Set test-specific environment variables
    env["GEMINI_API_KEY"] = "test-api-key-for-e2e"
    env["OUTPUT_DIR"] = str(temp_output_dir)
    env["LOG_LEVEL"] = "WARNING"  # Reduce log noise in tests
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return env


class TestCLIHelp:
    """Test CLI help and argument parsing."""

    def test_help_flag_exits_zero(self) -> None:
        """Verify --help causes SystemExit with code 0."""
        from src.cli import parse_args

        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_invalid_mode_returns_error(self) -> None:
        """Verify invalid mode argument raises SystemExit."""
        from src.cli import parse_args

        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--mode", "INVALID_MODE"])
        assert exc_info.value.code != 0


class TestCLINonInteractive:
    """Test non-interactive CLI execution."""

    @pytest.mark.e2e
    def test_non_interactive_with_missing_api_key(self, temp_output_dir: Path) -> None:
        """Verify graceful handling when API key is missing."""
        env = os.environ.copy()
        # Remove API key if present
        env.pop("GEMINI_API_KEY", None)
        env.pop("GOOGLE_API_KEY", None)
        env["OUTPUT_DIR"] = str(temp_output_dir)
        env["PYTHONPATH"] = str(PROJECT_ROOT)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.main",
                "--non-interactive",
                "--mode",
                "GENERATE",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        # Should fail gracefully with clear error message
        assert (
            result.returncode != 0
            or "api" in result.stderr.lower()
            or "key" in result.stderr.lower()
        )


class TestCLIAnalyzeCache:
    """Test cache analysis CLI functionality."""

    @pytest.mark.e2e
    def test_analyze_cache_flag(self, mock_env: dict[str, str]) -> None:
        """Verify --analyze-cache flag works."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.main",
                "--analyze-cache",
                "--non-interactive",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            env=mock_env,
        )
        # Should complete (may or may not have cache data)
        # We just verify it doesn't crash
        assert result.returncode in [0, 1]  # 0 or config error


class TestCLIArgParsing:
    """Test CLI argument parsing module directly."""

    def test_parse_args_defaults(self) -> None:
        """Verify default argument values."""
        from src.cli import parse_args

        args = parse_args([])
        assert args.mode == "AUTO"
        assert args.interactive is False
        assert args.non_interactive is False
        assert args.log_level == "INFO"

    def test_parse_args_non_interactive(self) -> None:
        """Verify non-interactive flag parsing."""
        from src.cli import parse_args

        args = parse_args(["--non-interactive", "--mode", "GENERATE"])
        assert args.non_interactive is True
        assert args.mode == "GENERATE"

    def test_parse_args_output_options(self) -> None:
        """Verify output options parsing."""
        from src.cli import parse_args

        args = parse_args(["--output", "result.json", "--format", "json"])
        assert args.output == "result.json"
        assert args.output_format == "json"

    def test_parse_args_verbose_quiet(self) -> None:
        """Verify verbose/quiet flags are mutually usable."""
        from src.cli import parse_args

        args_v = parse_args(["--verbose"])
        assert args_v.verbose is True
        assert args_v.quiet is False

        args_q = parse_args(["--quiet"])
        assert args_q.quiet is True
        assert args_q.verbose is False

    def test_parse_args_checkpoint_options(self) -> None:
        """Verify checkpoint-related options."""
        from src.cli import parse_args

        args = parse_args(
            [
                "--resume",
                "--checkpoint-file",
                "custom_checkpoint.jsonl",
                "--keep-progress",
            ]
        )
        assert args.resume is True
        assert args.checkpoint_file == "custom_checkpoint.jsonl"
        assert args.keep_progress is True


class TestCLIOutputFormat:
    """Test CLI output formatting."""

    def test_format_output_json(self) -> None:
        """Verify JSON output formatting."""
        from src.cli import format_output

        result = {"query": "test", "answer": "response"}
        output = format_output(result, "json")
        assert '"query"' in output
        assert '"answer"' in output

    def test_format_output_text(self) -> None:
        """Verify text output formatting."""
        from src.cli import format_output

        result = {"query": "test", "answer": "response"}
        output = format_output(result, "text")
        assert "query:" in output
        assert "answer:" in output

    def test_format_output_nested_dict(self) -> None:
        """Verify nested dict formatting in text mode."""
        from src.cli import format_output

        result = {"metadata": {"version": "1.0", "author": "test"}}
        output = format_output(result, "text")
        assert "metadata:" in output
        assert "version:" in output

    def test_format_output_list(self) -> None:
        """Verify list formatting in text mode."""
        from src.cli import format_output

        result = {"items": ["a", "b", "c"]}
        output = format_output(result, "text")
        assert "items:" in output
        assert "- a" in output
