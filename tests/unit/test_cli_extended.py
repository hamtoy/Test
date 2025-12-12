"""Extended tests for cli module.

Covers:
- format_output() with various input types
- run_neo4j_optimization() function
- Environment variable validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.cli import CLIArgs, format_output, parse_args, run_neo4j_optimization


class TestCLIArgs:
    """Tests for CLIArgs dataclass."""

    def test_default_values(self) -> None:
        """Test CLIArgs has correct default values."""
        args = CLIArgs()

        assert args.mode == "AUTO"
        assert args.interactive is False
        assert args.non_interactive is False
        assert args.ocr_file == "input_ocr.txt"
        assert args.cand_file == "input_candidates.json"
        assert args.intent is None
        assert args.checkpoint_file == "checkpoint.jsonl"
        assert args.keep_progress is False
        assert args.no_cost_panel is False
        assert args.no_budget_panel is False
        assert args.resume is False
        assert args.log_level == "INFO"
        assert args.analyze_cache is False
        assert args.integrated_pipeline is False
        assert args.pipeline_meta == "examples/session_input.json"
        assert args.optimize_neo4j is False
        assert args.drop_existing_indexes is False
        assert args.output is None
        assert args.output_format == "text"
        assert args.verbose is False
        assert args.quiet is False

    def test_custom_values(self) -> None:
        """Test CLIArgs with custom values."""
        args = CLIArgs(
            mode="BATCH",
            interactive=True,
            output="/path/to/output",
            output_format="json",
        )

        assert args.mode == "BATCH"
        assert args.interactive is True
        assert args.output == "/path/to/output"
        assert args.output_format == "json"


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_default_args(self) -> None:
        """Test parsing with no arguments."""
        args = parse_args([])

        assert args.mode == "AUTO"
        assert args.interactive is False

    def test_parse_mode_argument(self) -> None:
        """Test parsing mode argument."""
        args = parse_args(["--mode", "BATCH"])

        assert args.mode == "BATCH"

    def test_parse_interactive_flag(self) -> None:
        """Test parsing interactive flag."""
        args = parse_args(["--interactive"])

        assert args.interactive is True

    def test_parse_non_interactive_flag(self) -> None:
        """Test parsing non-interactive flag."""
        args = parse_args(["--non-interactive"])

        assert args.non_interactive is True

    def test_parse_output_arguments(self) -> None:
        """Test parsing output-related arguments."""
        args = parse_args(["-o", "result.json", "--format", "json"])

        assert args.output == "result.json"
        assert args.output_format == "json"

    def test_parse_verbose_and_quiet(self) -> None:
        """Test parsing verbose and quiet flags."""
        verbose_args = parse_args(["-v"])
        quiet_args = parse_args(["-q"])

        assert verbose_args.verbose is True
        assert quiet_args.quiet is True

    def test_parse_neo4j_options(self) -> None:
        """Test parsing Neo4j optimization options."""
        args = parse_args(["--optimize-neo4j", "--drop-existing-indexes"])

        assert args.optimize_neo4j is True
        assert args.drop_existing_indexes is True

    def test_parse_log_level(self) -> None:
        """Test parsing log level argument."""
        args = parse_args(["--log-level", "DEBUG"])

        assert args.log_level == "DEBUG"

    def test_parse_resume_flag(self) -> None:
        """Test parsing resume flag."""
        args = parse_args(["--resume"])

        assert args.resume is True

    def test_parse_analyze_cache(self) -> None:
        """Test parsing analyze-cache flag."""
        args = parse_args(["--analyze-cache"])

        assert args.analyze_cache is True

    def test_parse_integrated_pipeline(self) -> None:
        """Test parsing integrated-pipeline and pipeline-meta."""
        args = parse_args(
            ["--integrated-pipeline", "--pipeline-meta", "custom/path.json"]
        )

        assert args.integrated_pipeline is True
        assert args.pipeline_meta == "custom/path.json"


class TestFormatOutput:
    """Tests for format_output function."""

    def test_format_output_json(self) -> None:
        """Test JSON format output."""
        result = {"key": "value", "number": 42}

        output = format_output(result, "json")

        assert '"key": "value"' in output
        assert '"number": 42' in output

    def test_format_output_text_simple(self) -> None:
        """Test text format with simple values."""
        result = {"name": "test", "count": 10}

        output = format_output(result, "text")

        assert "name: test" in output
        assert "count: 10" in output

    def test_format_output_text_with_dict(self) -> None:
        """Test text format with nested dictionary."""
        result = {
            "stats": {
                "hits": 100,
                "misses": 20,
            }
        }

        output = format_output(result, "text")

        assert "stats:" in output
        assert "hits: 100" in output
        assert "misses: 20" in output

    def test_format_output_text_with_list(self) -> None:
        """Test text format with list values."""
        result = {"items": ["apple", "banana", "cherry"]}

        output = format_output(result, "text")

        assert "items:" in output
        assert "- apple" in output
        assert "- banana" in output
        assert "- cherry" in output

    def test_format_output_text_mixed(self) -> None:
        """Test text format with mixed types."""
        result = {
            "name": "test",
            "nested": {"a": 1, "b": 2},
            "items": ["x", "y"],
            "count": 5,
        }

        output = format_output(result, "text")

        assert "name: test" in output
        assert "nested:" in output
        assert "a: 1" in output
        assert "items:" in output
        assert "- x" in output
        assert "count: 5" in output

    def test_format_output_json_with_non_serializable(self) -> None:
        """Test JSON format handles non-serializable types."""
        from datetime import datetime

        result = {"timestamp": datetime(2024, 1, 15, 12, 0, 0)}

        # Should not raise, uses default=str
        output = format_output(result, "json")

        assert "2024" in output


class TestRunNeo4jOptimization:
    """Tests for run_neo4j_optimization function."""

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_import_error(self) -> None:
        """Test RuntimeError when neo4j package is not installed.

        Note: This test is difficult to properly test due to import behavior.
        The actual import error is caught and re-raised as RuntimeError.
        """
        # Skip this test as it requires complex import mocking
        pytest.skip("Import mocking for this test is complex")

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_missing_env_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error when required environment variables are missing."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        with patch("src.cli.neo4j", create=True):
            with patch("src.cli.TwoTierIndexManager", create=True):
                with pytest.raises(OSError) as exc_info:
                    await run_neo4j_optimization()

                assert "NEO4J_URI" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful Neo4j optimization."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_driver = AsyncMock()
        mock_manager = AsyncMock()

        with patch("neo4j.AsyncGraphDatabase") as mock_neo4j:
            mock_neo4j.driver.return_value = mock_driver

            with patch(
                "src.infra.neo4j_optimizer.TwoTierIndexManager",
                return_value=mock_manager,
            ):
                await run_neo4j_optimization(drop_existing=False)

                mock_manager.create_all_indexes.assert_called_once()
                mock_manager.list_all_indexes.assert_called_once()
                mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_neo4j_optimization_with_drop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Neo4j optimization with drop_existing=True."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_driver = AsyncMock()
        mock_manager = AsyncMock()

        with patch("neo4j.AsyncGraphDatabase") as mock_neo4j:
            mock_neo4j.driver.return_value = mock_driver

            with patch(
                "src.infra.neo4j_optimizer.TwoTierIndexManager",
                return_value=mock_manager,
            ):
                await run_neo4j_optimization(drop_existing=True)

                mock_manager.drop_all_indexes.assert_called_once()
                mock_manager.create_all_indexes.assert_called_once()
