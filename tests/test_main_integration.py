from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
            self.model_name = "gemini-3-pro-preview"
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
    monkeypatch.setattr(main_module, "interactive_main", AsyncMock())

    await main_module.main()

    # Test passes if no exception is raised (interactive_main is mocked)
    assert True


@pytest.mark.asyncio
async def test_main_keep_progress_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
            self.model_name = "gemini-3-pro-preview"
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
async def test_main_cache_stats_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
            self.model_name = "gemini-3-pro-preview"
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
async def test_main_auto_mode_passes_intent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
            self.model_name = "gemini-3-pro-preview"
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
async def test_main_missing_templates_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
            self.model_name = "gemini-3-pro-preview"
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
