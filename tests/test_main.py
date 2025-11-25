import asyncio
import pytest
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
from src.main import execute_workflow, save_result_to_file, _gather_results
from src.utils import load_checkpoint, append_checkpoint
from src.models import WorkflowResult, EvaluationResultSchema, EvaluationItem
from src.exceptions import BudgetExceededError


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.generate_query = AsyncMock(return_value=["Query 1"])
    agent.evaluate_responses = AsyncMock()
    agent.rewrite_best_answer = AsyncMock(return_value="Rewritten Answer")
    agent.create_context_cache = AsyncMock(return_value=None)
    agent.get_total_cost = MagicMock(return_value=0.1)
    agent.get_budget_usage_percent = MagicMock(return_value=50.0)
    agent.check_budget = MagicMock(return_value=None)
    return agent


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.mark.asyncio
async def test_execute_workflow_success(mock_agent, mock_logger):
    ocr_text = "ocr"
    candidates = {"A": "a", "B": "b", "C": "c"}

    # Mock evaluation result
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    mock_agent.evaluate_responses.return_value = eval_result

    with patch("src.main.reload_data_if_needed", new_callable=AsyncMock) as mock_reload:
        mock_reload.return_value = (ocr_text, candidates)

        # Mock save_result_to_file to avoid file I/O
        with patch("src.main.save_result_to_file") as mock_save:
            results = await execute_workflow(
                agent=mock_agent,
                ocr_text=ocr_text,
                user_intent=None,
                logger=mock_logger,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                config=None,
                is_interactive=False,
            )

            assert len(results) == 1
            assert results[0].query == "Query 1"
            assert results[0].best_answer == "a"
            assert results[0].rewritten_answer == "Rewritten Answer"
            mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_execute_workflow_query_gen_fail(mock_agent, mock_logger):
    mock_agent.generate_query.return_value = []

    results = await execute_workflow(
        agent=mock_agent,
        ocr_text="ocr",
        user_intent=None,
        logger=mock_logger,
        ocr_filename="ocr.txt",
        cand_filename="cand.json",
        config=None,
        is_interactive=False,
    )

    assert len(results) == 0
    mock_logger.error.assert_called_with("질의 생성 실패")


@pytest.mark.asyncio
async def test_execute_workflow_budget_exceeded(mock_logger):
    mock_agent = MagicMock()
    mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
    mock_agent.check_budget = MagicMock(side_effect=BudgetExceededError("limit"))
    mock_agent.get_budget_usage_percent = MagicMock(return_value=95.0)
    mock_agent.create_context_cache = AsyncMock(return_value=None)

    with patch("src.main.reload_data_if_needed", new_callable=AsyncMock) as mock_reload:
        mock_reload.return_value = ("ocr", {"A": "a"})

        results = await execute_workflow(
            agent=mock_agent,
            ocr_text="ocr",
            user_intent=None,
            logger=mock_logger,
            ocr_filename="ocr.txt",
            cand_filename="cand.json",
            config=None,
            is_interactive=False,
        )

    assert results == []
    mock_logger.error.assert_any_call("Budget limit exceeded: limit")


@pytest.mark.asyncio
async def test_gather_results_propagates_budget_error(mock_logger):
    async def _raise_budget():
        raise BudgetExceededError("limit")

    task = asyncio.create_task(_raise_budget())
    with pytest.raises(BudgetExceededError):
        await _gather_results([task], mock_logger)


@pytest.mark.asyncio
async def test_execute_workflow_interactive_skip_reload(mock_agent, mock_logger):
    mock_agent.create_context_cache = AsyncMock(return_value=None)
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    mock_agent.evaluate_responses = AsyncMock(return_value=eval_result)
    mock_agent.rewrite_best_answer = AsyncMock(return_value="rewritten")

    with (
        patch("src.main.Confirm.ask", return_value=False),
        patch("src.main.reload_data_if_needed", new_callable=AsyncMock) as mock_reload,
    ):
        mock_reload.return_value = ("ocr", {"A": "a"})

        results = await execute_workflow(
            agent=mock_agent,
            ocr_text="ocr",
            user_intent=None,
            logger=mock_logger,
            ocr_filename="ocr.txt",
            cand_filename="cand.json",
            config=None,
            is_interactive=True,
        )

    assert len(results) == 1
    mock_reload.assert_called_once()
    mock_agent.rewrite_best_answer.assert_awaited()


@pytest.mark.asyncio
async def test_main_analyze_cache_quick_path(monkeypatch, tmp_path):
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)

    calls: dict[str, object] = {}

    class FakeConfig:
        def __init__(self):
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-3-pro-preview"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config, jinja_env):
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
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)
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
        ),
    )

    await main_module.main()

    assert calls.get("printed") == {"total": 1}


@pytest.mark.asyncio
async def test_main_keep_progress_flag(monkeypatch, tmp_path):
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self):
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-3-pro-preview"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config, jinja_env):
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    execute_spy = AsyncMock(return_value=[])
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
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a", "B": "b", "C": "c"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", execute_spy)
    monkeypatch.setattr(main_module, "_render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)
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
        ),
    )

    await main_module.main()

    execute_spy.assert_awaited_once()
    _, kwargs = execute_spy.await_args
    assert kwargs["keep_progress"] is True


@pytest.mark.asyncio
async def test_main_cache_stats_warning(monkeypatch, tmp_path):
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self):
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-3-pro-preview"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config, jinja_env):
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

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
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a", "B": "b", "C": "c"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_module, "_render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)
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
        ),
    )
    monkeypatch.setattr(
        main_module,
        "write_cache_stats",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    await main_module.main()

    logger.warning.assert_called()


@pytest.mark.asyncio
async def test_main_auto_mode_passes_intent(monkeypatch, tmp_path):
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "templates"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    for d in (template_dir, input_dir, output_dir):
        d.mkdir(parents=True, exist_ok=True)
    (template_dir / "placeholder.j2").write_text("content", encoding="utf-8")

    class FakeConfig:
        def __init__(self):
            self.api_key = "AIza" + "0" * 35
            self.template_dir = template_dir
            self.input_dir = input_dir
            self.output_dir = output_dir
            self.model_name = "gemini-3-pro-preview"
            self.cache_stats_path = tmp_path / "stats.jsonl"
            self.cache_stats_max_entries = 3

    class FakeAgent:
        def __init__(self, config, jinja_env):
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.cache_hits = 0
            self.cache_misses = 0

    execute_spy = AsyncMock(return_value=[])
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
    monkeypatch.setattr(main_module, "GeminiAgent", FakeAgent)
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(
        main_module,
        "load_input_data",
        AsyncMock(return_value=("ocr", {"A": "a"})),
    )
    monkeypatch.setattr(main_module, "execute_workflow", execute_spy)
    monkeypatch.setattr(main_module, "_render_cost_panel", lambda agent: "panel")
    monkeypatch.setattr(main_module.console, "print", lambda *args, **kwargs: None)
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
        ),
    )

    await main_module.main()

    args, kwargs = execute_spy.await_args
    assert args[2] == "요약"


@pytest.mark.asyncio
async def test_main_missing_templates_exits(monkeypatch, tmp_path):
    import src.main as main_module
    from src.cli import CLIArgs

    template_dir = tmp_path / "missing"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    class FakeConfig:
        def __init__(self):
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
    monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)
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
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        await main_module.main()

    assert excinfo.value.code == 1
    logger.critical.assert_called()


def test_save_result_to_file(tmp_path):
    config = MagicMock()
    config.output_dir = tmp_path

    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])

    result = WorkflowResult(
        turn_id=1,
        query="Test Query",
        evaluation=eval_result,
        best_answer="Best Answer",
        rewritten_answer="Rewritten",
        cost=0.05,
        success=True,
    )

    save_result_to_file(result, config)

    # Check if file was created
    files = list(tmp_path.glob("result_turn_1_*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Test Query" in content
    assert "Rewritten" in content


def test_save_result_to_file_io_error(monkeypatch, tmp_path):
    config = MagicMock()
    config.output_dir = tmp_path

    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])

    result = WorkflowResult(
        turn_id=1,
        query="Test Query",
        evaluation=eval_result,
        best_answer="Best Answer",
        rewritten_answer="Rewritten",
        cost=0.05,
        success=True,
    )

    monkeypatch.setattr("builtins.open", MagicMock(side_effect=PermissionError))
    with pytest.raises(PermissionError):
        save_result_to_file(result, config)


@pytest.mark.asyncio
async def test_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "checkpoint.jsonl"
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    result = WorkflowResult(
        turn_id=1,
        query="Query",
        evaluation=eval_result,
        best_answer="A",
        rewritten_answer="A",
        cost=0.0,
        success=True,
    )

    await append_checkpoint(path, result)
    loaded = await load_checkpoint(path)
    assert "Query" in loaded
    assert loaded["Query"].turn_id == 1
