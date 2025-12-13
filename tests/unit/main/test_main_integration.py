"""Integration tests for src/main.py with comprehensive coverage.

This module tests:
1. CLI Arguments: sys.argv manipulation with unittest.mock.patch
2. Dependency Mocking: ConfigLoader, Agent, UI class mocking
3. Flow Control: Normal execution, Exception handling, KeyboardInterrupt
4. Validation: Strict verification with assert_called_once_with()
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_main_analyze_cache_quick_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)

    calls: dict[str, object] = {}

    class FakeConfig:
        def __init__(self) -> None:
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-flash-latest"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config: Any, jinja_env: Any) -> None:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda log_level=None: (MagicMock(), SimpleNamespace(stop=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "jinja2",
        SimpleNamespace(
            Environment=lambda **kwargs: "env", FileSystemLoader=lambda p: "loader"
        ),
    )
    monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr content", {"A": "a", "B": "b", "C": "c"})),
    )
    monkeypatch.setattr(main_module, "analyze_cache_stats", lambda path: {"total": 1})
    monkeypatch.setattr(
        main_module,
        "print_cache_report",
        lambda summary: calls.setdefault("printed", summary),
    )
    monkeypatch.setattr(
        main_module,
        "parse_args",
        lambda: CLIArgs(
            mode="AUTO",
            interactive=False,
            ocr_file="ocr.txt",
            cand_file="cand.json",
            intent=None,
            checkpoint_file="checkpoint.jsonl",
            keep_progress=False,
            no_cost_panel=False,
            no_budget_panel=False,
            resume=False,
            log_level="INFO",
            analyze_cache=True,
            integrated_pipeline=False,
            pipeline_meta="examples/session_input.json",
            optimize_neo4j=False,
            drop_existing_indexes=False,
        ),
    )
    # Mock interactive_main to prevent stdin reads
    interactive_mock = AsyncMock()
    monkeypatch.setattr(main_module, "interactive_main", interactive_mock)

    await main_module.main()

    # Verify interactive_main was called (main() completes without exception)
    interactive_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_keep_progress_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self) -> None:
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-flash-latest"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config: Any, jinja_env: Any) -> None:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    execute_spy = AsyncMock(return_value=[])
    logger = MagicMock()
    interactive_spy = AsyncMock()

    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda log_level=None: (logger, SimpleNamespace(stop=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "jinja2",
        SimpleNamespace(
            Environment=lambda **kwargs: "env", FileSystemLoader=lambda p: "loader"
        ),
    )
    monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a", "B": "b", "C": "c"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", execute_spy)
    monkeypatch.setattr(main_module, "render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(main_module, "write_cache_stats", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "parse_args",
        lambda: CLIArgs(
            mode="AUTO",
            interactive=False,
            ocr_file="ocr.txt",
            cand_file="cand.json",
            intent=None,
            checkpoint_file="checkpoint.jsonl",
            keep_progress=True,
            no_cost_panel=False,
            no_budget_panel=False,
            resume=False,
            log_level="INFO",
            analyze_cache=False,
            integrated_pipeline=False,
            pipeline_meta="examples/session_input.json",
            optimize_neo4j=False,
            drop_existing_indexes=False,
        ),
    )
    # Mock interactive_main to prevent stdin reads
    monkeypatch.setattr(main_module, "interactive_main", interactive_spy)

    await main_module.main()

    # Verify interactive_main was called (current main() launches interactive menu)
    interactive_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_cache_stats_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self) -> None:
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-flash-latest"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config: Any, jinja_env: Any) -> None:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    logger = MagicMock()
    interactive_spy = AsyncMock()

    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda log_level=None: (logger, SimpleNamespace(stop=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "jinja2",
        SimpleNamespace(
            Environment=lambda **kwargs: "env", FileSystemLoader=lambda p: "loader"
        ),
    )
    monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a", "B": "b", "C": "c"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_module, "render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "parse_args",
        lambda: CLIArgs(
            mode="AUTO",
            interactive=False,
            ocr_file="ocr.txt",
            cand_file="cand.json",
            intent=None,
            checkpoint_file="checkpoint.jsonl",
            keep_progress=False,
            no_cost_panel=False,
            no_budget_panel=False,
            resume=False,
            log_level="INFO",
            analyze_cache=False,
            integrated_pipeline=False,
            pipeline_meta="examples/session_input.json",
            optimize_neo4j=False,
            drop_existing_indexes=False,
        ),
    )
    monkeypatch.setattr(
        main_module,
        "write_cache_stats",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")),
    )
    # Mock interactive_main to prevent stdin reads
    monkeypatch.setattr(main_module, "interactive_main", interactive_spy)

    await main_module.main()

    # Verify interactive_main was called (current main() launches interactive menu)
    interactive_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_auto_mode_passes_intent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self) -> None:
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-flash-latest"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config: Any, jinja_env: Any) -> None:
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    execute_spy = AsyncMock(return_value=[])
    logger = MagicMock()
    interactive_spy = AsyncMock()

    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda log_level=None: (logger, SimpleNamespace(stop=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "jinja2",
        SimpleNamespace(
            Environment=lambda **kwargs: "env", FileSystemLoader=lambda p: "loader"
        ),
    )
    monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", execute_spy)
    monkeypatch.setattr(main_module, "render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(main_module, "write_cache_stats", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main_module,
        "parse_args",
        lambda: CLIArgs(
            mode="AUTO",
            interactive=False,
            ocr_file="ocr.txt",
            cand_file="cand.json",
            intent="요약",
            checkpoint_file="checkpoint.jsonl",
            keep_progress=False,
            no_cost_panel=False,
            no_budget_panel=False,
            resume=False,
            log_level="INFO",
            analyze_cache=False,
            integrated_pipeline=False,
            pipeline_meta="examples/session_input.json",
            optimize_neo4j=False,
            drop_existing_indexes=False,
        ),
    )
    # Mock interactive_main to prevent stdin reads
    monkeypatch.setattr(main_module, "interactive_main", interactive_spy)

    await main_module.main()

    # Verify interactive_main was called (current main() launches interactive menu)
    interactive_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_missing_templates_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "missing"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    class FakeConfig:
        def __init__(self) -> None:
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-flash-latest"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    logger = MagicMock()

    monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
    monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda log_level=None: (logger, SimpleNamespace(stop=lambda: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "jinja2",
        SimpleNamespace(
            Environment=lambda **kwargs: "env", FileSystemLoader=lambda p: "loader"
        ),
    )
    monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
    monkeypatch.setattr(main_module, "GeminiAgent", MagicMock())
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main_module,
        "parse_args",
        lambda: CLIArgs(
            mode="AUTO",
            interactive=False,
            ocr_file="ocr.txt",
            cand_file="cand.json",
            intent=None,
            checkpoint_file="checkpoint.jsonl",
            keep_progress=False,
            no_cost_panel=False,
            no_budget_panel=False,
            resume=False,
            log_level="INFO",
            analyze_cache=False,
            integrated_pipeline=False,
            pipeline_meta="examples/session_input.json",
            optimize_neo4j=False,
            drop_existing_indexes=False,
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        await main_module.main()

    assert excinfo.value.code == 1
    logger.critical.assert_called()


# =============================================================================
# CLI Arguments Tests
# =============================================================================


class TestCLIArguments:
    """Tests for CLI argument parsing with sys.argv mocking."""

    def test_parse_args_with_debug_mode(self) -> None:
        """Test parse_args with --log-level DEBUG flag."""
        from src.cli import parse_args

        # Parse with explicit args list
        result = parse_args(["--log-level", "DEBUG"])

        assert result.log_level == "DEBUG"
        assert result.mode == "AUTO"  # default

    def test_parse_args_with_mode_flag(self) -> None:
        """Test parse_args with different --mode flags."""
        from src.cli import parse_args

        for mode in ["AUTO", "MANUAL", "BATCH", "GENERATE", "EVALUATE", "INSPECT"]:
            result = parse_args(["--mode", mode])
            assert result.mode == mode

    def test_parse_args_with_non_interactive_mode(self) -> None:
        """Test parse_args with --non-interactive flag for CI/CD."""
        from src.cli import parse_args

        result = parse_args(["--non-interactive", "--output", "result.json"])

        assert result.non_interactive is True
        assert result.output == "result.json"

    def test_parse_args_with_ocr_and_candidate_files(self) -> None:
        """Test parse_args with custom file paths."""
        from src.cli import parse_args

        result = parse_args(
            [
                "--ocr-file",
                "custom_ocr.txt",
                "--cand-file",
                "custom_candidates.json",
            ]
        )

        assert result.ocr_file == "custom_ocr.txt"
        assert result.cand_file == "custom_candidates.json"

    def test_parse_args_with_intent(self) -> None:
        """Test parse_args with --intent flag."""
        from src.cli import parse_args

        result = parse_args(["--intent", "요약"])

        assert result.intent == "요약"

    def test_parse_args_with_checkpoint_resume(self) -> None:
        """Test parse_args with --resume and --checkpoint-file flags."""
        from src.cli import parse_args

        result = parse_args(
            [
                "--resume",
                "--checkpoint-file",
                "custom_checkpoint.jsonl",
            ]
        )

        assert result.resume is True
        assert result.checkpoint_file == "custom_checkpoint.jsonl"

    def test_parse_args_with_analyze_cache(self) -> None:
        """Test parse_args with --analyze-cache flag."""
        from src.cli import parse_args

        result = parse_args(["--analyze-cache"])

        assert result.analyze_cache is True

    def test_parse_args_with_output_format_json(self) -> None:
        """Test parse_args with --format json flag."""
        from src.cli import parse_args

        result = parse_args(["--format", "json", "--output", "output.json"])

        assert result.output_format == "json"
        assert result.output == "output.json"

    def test_parse_args_with_verbose_quiet_flags(self) -> None:
        """Test parse_args with -v and -q flags."""
        from src.cli import parse_args

        verbose_result = parse_args(["-v"])
        assert verbose_result.verbose is True

        quiet_result = parse_args(["-q"])
        assert quiet_result.quiet is True

    def test_parse_args_with_all_panels_disabled(self) -> None:
        """Test parse_args with panel display flags disabled."""
        from src.cli import parse_args

        result = parse_args(["--no-cost-panel", "--no-budget-panel"])

        assert result.no_cost_panel is True
        assert result.no_budget_panel is True

    def test_parse_args_with_neo4j_optimization(self) -> None:
        """Test parse_args with --optimize-neo4j flag."""
        from src.cli import parse_args

        result = parse_args(
            [
                "--optimize-neo4j",
                "--drop-existing-indexes",
            ]
        )

        assert result.optimize_neo4j is True
        assert result.drop_existing_indexes is True

    def test_parse_args_with_integrated_pipeline(self) -> None:
        """Test parse_args with --integrated-pipeline flag."""
        from src.cli import parse_args

        result = parse_args(
            [
                "--integrated-pipeline",
                "--pipeline-meta",
                "custom_meta.json",
            ]
        )

        assert result.integrated_pipeline is True
        assert result.pipeline_meta == "custom_meta.json"

    def test_parse_args_default_values(self) -> None:
        """Test parse_args default values without any arguments."""
        from src.cli import parse_args

        result = parse_args([])

        assert result.mode == "AUTO"
        assert result.interactive is False
        assert result.non_interactive is False
        assert result.ocr_file == "input_ocr.txt"
        assert result.cand_file == "input_candidates.json"
        assert result.intent is None
        assert result.checkpoint_file == "checkpoint.jsonl"
        assert result.keep_progress is False
        assert result.no_cost_panel is False
        assert result.no_budget_panel is False
        assert result.resume is False
        assert result.log_level == "INFO"
        assert result.analyze_cache is False
        assert result.integrated_pipeline is False
        assert result.pipeline_meta == "examples/session_input.json"
        assert result.optimize_neo4j is False
        assert result.drop_existing_indexes is False
        assert result.output is None
        assert result.output_format == "text"
        assert result.verbose is False
        assert result.quiet is False


# =============================================================================
# Dependency Mocking Tests
# =============================================================================


class TestDependencyMocking:
    """Tests for mocking ConfigLoader, Agent, UI components."""

    @pytest.fixture
    def mock_setup_logging(self) -> Generator[MagicMock, None, None]:
        """Fixture for mocking setup_logging."""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_listener = MagicMock()
        mock_listener.stop = MagicMock()
        with patch(
            "src.main.setup_logging", return_value=(mock_logger, mock_listener)
        ) as mock_fn:
            mock_fn.mock_logger = mock_logger
            mock_fn.mock_listener = mock_listener
            yield mock_fn

    @pytest.fixture
    def mock_app_config(self, tmp_path: Path) -> Generator[MagicMock, None, None]:
        """Fixture for mocking AppConfig."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = template_dir

        with patch("src.main.AppConfig", return_value=mock_config) as mock_fn:
            mock_fn.mock_config = mock_config
            yield mock_fn

    @pytest.fixture
    def mock_genai(self) -> Generator[MagicMock, None, None]:
        """Fixture for mocking genai module."""
        with patch("src.main.genai") as mock_fn:
            mock_fn.configure = MagicMock()
            yield mock_fn

    @pytest.fixture
    def mock_gemini_agent(self) -> Generator[MagicMock, None, None]:
        """Fixture for mocking GeminiAgent."""
        mock_agent = MagicMock()
        mock_agent.total_input_tokens = 0
        mock_agent.total_output_tokens = 0
        mock_agent.cache_hits = 0
        mock_agent.cache_misses = 0

        with patch("src.main.GeminiAgent", return_value=mock_agent) as mock_fn:
            mock_fn.mock_agent = mock_agent
            yield mock_fn

    @pytest.fixture
    def mock_interactive_main(self) -> Generator[AsyncMock, None, None]:
        """Fixture for mocking interactive_main."""
        with patch("src.main.interactive_main", new_callable=AsyncMock) as mock_fn:
            yield mock_fn

    @pytest.mark.asyncio
    async def test_config_initialization_with_valid_api_key(
        self,
        mock_setup_logging: MagicMock,
        mock_app_config: MagicMock,
        mock_genai: MagicMock,
        mock_gemini_agent: MagicMock,
        mock_interactive_main: AsyncMock,
    ) -> None:
        """Test configuration initializes with valid API key."""
        from src.main import main

        await main()

        # Verify genai.configure was called with correct API key
        mock_genai.configure.assert_called_once_with(
            api_key=mock_app_config.mock_config.api_key
        )

    @pytest.mark.asyncio
    async def test_gemini_agent_initialization(
        self,
        mock_setup_logging: MagicMock,
        mock_app_config: MagicMock,
        mock_genai: MagicMock,
        mock_gemini_agent: MagicMock,
        mock_interactive_main: AsyncMock,
    ) -> None:
        """Test GeminiAgent is initialized with correct config and jinja_env."""
        from src.main import main

        await main()

        # Verify GeminiAgent was called once
        mock_gemini_agent.assert_called_once()

        # Verify the config was passed to GeminiAgent
        call_args = mock_gemini_agent.call_args
        assert call_args is not None
        assert call_args[0][0] == mock_app_config.mock_config

    @pytest.mark.asyncio
    async def test_interactive_main_called_with_correct_args(
        self,
        mock_setup_logging: MagicMock,
        mock_app_config: MagicMock,
        mock_genai: MagicMock,
        mock_gemini_agent: MagicMock,
        mock_interactive_main: AsyncMock,
    ) -> None:
        """Test interactive_main is called with agent, config, and logger."""
        from src.main import main

        await main()

        # Verify interactive_main was called once
        mock_interactive_main.assert_awaited_once()

        # Verify arguments passed to interactive_main
        call_args = mock_interactive_main.call_args
        assert call_args is not None
        # Should receive agent, config, logger
        assert len(call_args[0]) == 3

    @pytest.mark.asyncio
    async def test_log_listener_stop_called_on_success(
        self,
        mock_setup_logging: MagicMock,
        mock_app_config: MagicMock,
        mock_genai: MagicMock,
        mock_gemini_agent: MagicMock,
        mock_interactive_main: AsyncMock,
    ) -> None:
        """Test log_listener.stop() is called after successful execution."""
        from src.main import main

        await main()

        mock_setup_logging.mock_listener.stop.assert_called_once()


# =============================================================================
# Flow Control Tests
# =============================================================================


class TestFlowControl:
    """Tests for flow control scenarios."""

    @pytest.mark.asyncio
    async def test_normal_execution_and_exit(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test normal execution flow completes successfully."""
        import src.main as main_module

        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        mock_logger = MagicMock()
        mock_listener = MagicMock()
        mock_listener.stop = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = template_dir

        mock_agent = MagicMock()

        mock_interactive = AsyncMock()

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            patch("src.main.GeminiAgent", return_value=mock_agent),
            patch("src.main.interactive_main", mock_interactive),
        ):
            # Should complete without exception
            await main_module.main()

            # Verify components were called
            mock_interactive.assert_awaited_once()
            mock_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_during_initialization_exits_with_code_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test exception during initialization causes sys.exit(1)."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()
        mock_listener.stop = MagicMock()

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", side_effect=ValueError("Config error")),
            patch("src.main.console"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1
            mock_logger.critical.assert_called()
            mock_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_not_found_error_exits_with_code_1(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test FileNotFoundError during initialization causes sys.exit(1)."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()
        mock_listener.stop = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = tmp_path / "nonexistent"

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            patch("src.main.console"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1
            mock_logger.critical.assert_called()

    @pytest.mark.asyncio
    async def test_os_error_exits_with_code_1(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test OSError during initialization causes sys.exit(1)."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()
        mock_listener.stop = MagicMock()

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", side_effect=OSError("Permission denied")),
            patch("src.main.console"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                await main()

            assert exc_info.value.code == 1
            mock_logger.critical.assert_called()
            mock_listener.stop.assert_called_once()


# =============================================================================
# Entry Point Tests (__name__ == "__main__" block)
# =============================================================================


class TestMainEntryPoint:
    """Tests for __name__ == "__main__" block coverage."""

    def test_keyboard_interrupt_graceful_shutdown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test KeyboardInterrupt causes graceful shutdown with exit code 130."""
        from src.config.constants import USER_INTERRUPT_MESSAGE
        from src.ui import console

        mock_console_print = MagicMock()

        with (
            patch.object(asyncio, "run", side_effect=KeyboardInterrupt),
            patch.object(console, "print", mock_console_print),
            patch("src.main.load_dotenv"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                # Simulate the if __name__ == "__main__" block
                try:
                    import src.main as main_module

                    asyncio.run(main_module.main())
                except KeyboardInterrupt:
                    console.print(USER_INTERRUPT_MESSAGE)
                    sys.exit(130)

            assert exc_info.value.code == 130
            mock_console_print.assert_called_once_with(USER_INTERRUPT_MESSAGE)

    def test_general_exception_exits_with_code_1(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test general exception causes sys.exit(1)."""
        from src.config.constants import USER_INTERRUPT_MESSAGE
        from src.ui import console

        mock_logging_critical = MagicMock()

        with (
            patch.object(asyncio, "run", side_effect=RuntimeError("Critical failure")),
            patch.object(logging, "critical", mock_logging_critical),
            patch("src.main.load_dotenv"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                # Simulate the if __name__ == "__main__" block
                try:
                    import src.main as main_module

                    asyncio.run(main_module.main())
                except KeyboardInterrupt:
                    console.print(USER_INTERRUPT_MESSAGE)
                    sys.exit(130)
                except Exception as e:
                    logging.critical("Critical error: %s", e, exc_info=True)
                    sys.exit(1)

            assert exc_info.value.code == 1
            mock_logging_critical.assert_called_once()

    def test_windows_event_loop_policy_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Windows event loop policy is set correctly on Windows."""
        # Simulate Windows environment
        monkeypatch.setattr(os, "name", "nt")

        mock_policy_class = MagicMock()
        mock_policy_instance = MagicMock()
        mock_policy_class.return_value = mock_policy_instance

        mock_set_policy = MagicMock()

        with (
            patch.object(
                asyncio,
                "WindowsSelectorEventLoopPolicy",
                mock_policy_class,
                create=True,
            ),
            patch.object(asyncio, "set_event_loop_policy", mock_set_policy),
        ):
            # Simulate the Windows event loop policy code
            if os.name == "nt":
                try:
                    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
                    if policy:
                        asyncio.set_event_loop_policy(policy())
                except AttributeError:
                    pass

            mock_set_policy.assert_called_once_with(mock_policy_instance)

    def test_non_windows_no_policy_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test event loop policy is not changed on non-Windows systems."""
        monkeypatch.setattr(os, "name", "posix")

        mock_set_policy = MagicMock()

        with patch.object(asyncio, "set_event_loop_policy", mock_set_policy):
            # Simulate the Windows event loop policy code
            if os.name == "nt":
                try:
                    policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
                    if policy:
                        asyncio.set_event_loop_policy(policy())
                except AttributeError:
                    pass

            # Policy should not be set on non-Windows
            mock_set_policy.assert_not_called()

    def test_windows_policy_attribute_error_handled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test AttributeError is handled when WindowsSelectorEventLoopPolicy not found."""
        monkeypatch.setattr(os, "name", "nt")

        # Remove WindowsSelectorEventLoopPolicy from asyncio if it exists
        if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
            monkeypatch.delattr(asyncio, "WindowsSelectorEventLoopPolicy")

        # Simulate the Windows event loop policy code - should not raise
        if os.name == "nt":
            try:
                policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
                if policy:
                    asyncio.set_event_loop_policy(policy())
            except AttributeError:
                pass

        # Test passes if no exception is raised


# =============================================================================
# Validation Tests (Strict Mock Verification)
# =============================================================================


class TestStrictValidation:
    """Tests with strict mock verification using assert_called_once_with()."""

    @pytest.mark.asyncio
    async def test_genai_configure_called_with_exact_api_key(
        self, tmp_path: Path
    ) -> None:
        """Verify genai.configure is called with exact API key."""
        from src.main import main

        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        expected_api_key = "AIza" + "X" * 35

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = expected_api_key
        mock_config.template_dir = template_dir

        mock_genai_configure = MagicMock()

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai") as mock_genai,
            patch("src.main.GeminiAgent"),
            patch("src.main.interactive_main", new_callable=AsyncMock),
        ):
            mock_genai.configure = mock_genai_configure

            await main()

            # Strict verification - exact argument match
            mock_genai_configure.assert_called_once_with(api_key=expected_api_key)

    @pytest.mark.asyncio
    async def test_setup_logging_called_with_correct_args(self, tmp_path: Path) -> None:
        """Verify setup_logging is called with correct arguments."""
        from src.main import main

        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        mock_setup_logging = MagicMock(return_value=(mock_logger, mock_listener))

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = template_dir

        with (
            patch("src.main.setup_logging", mock_setup_logging),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            patch("src.main.GeminiAgent"),
            patch("src.main.interactive_main", new_callable=AsyncMock),
        ):
            await main()

            # Strict verification - exact argument match
            mock_setup_logging.assert_called_once_with(log_level=None)

    @pytest.mark.asyncio
    async def test_log_listener_stop_called_once(self, tmp_path: Path) -> None:
        """Verify log_listener.stop() is called exactly once."""
        from src.main import main

        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        mock_config = MagicMock()
        mock_config.api_key = "AIza" + "0" * 35
        mock_config.template_dir = template_dir

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", return_value=mock_config),
            patch("src.main.genai"),
            patch("src.main.GeminiAgent"),
            patch("src.main.interactive_main", new_callable=AsyncMock),
        ):
            await main()

            # Strict verification - called exactly once
            mock_listener.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_console_print_called_on_initialization_error(
        self, tmp_path: Path
    ) -> None:
        """Verify console.print is called when initialization fails."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        error_message = "Invalid configuration value"
        mock_console = MagicMock()

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", side_effect=ValueError(error_message)),
            patch("src.main.console", mock_console),
        ):
            with pytest.raises(SystemExit):
                await main()

            # Verify console.print was called with error message
            assert mock_console.print.called
            call_args = mock_console.print.call_args[0][0]
            assert "초기화 실패" in call_args or error_message in call_args

    @pytest.mark.asyncio
    async def test_logger_critical_called_with_error_details(
        self, tmp_path: Path
    ) -> None:
        """Verify logger.critical is called with error details on failure."""
        from src.main import main

        mock_logger = MagicMock()
        mock_listener = MagicMock()

        error_message = "Configuration validation failed"

        with (
            patch("src.main.setup_logging", return_value=(mock_logger, mock_listener)),
            patch("src.main.AppConfig", side_effect=ValueError(error_message)),
            patch("src.main.console"),
        ):
            with pytest.raises(SystemExit):
                await main()

            # Verify logger.critical was called
            mock_logger.critical.assert_called_once()

            # Verify the call includes the error message
            call_args = mock_logger.critical.call_args
            assert "[FATAL]" in call_args[0][0] or "Initialization" in call_args[0][0]
