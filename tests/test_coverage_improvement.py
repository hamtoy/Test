"""Tests to improve coverage for modules below 80%.

Targets:
- src/automation/promote_rules.py (68% → target 80%)
- src/infra/worker.py (69% → target 80%)
- src/main.py (69% → target 80%)
- src/graph/data2neo_extractor.py (75% → target 80%)
- src/workflow/executor.py (75% → target 80%)

Note: src/web/api.py tests are in test_web_api.py
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Tests for src/automation/promote_rules.py
# =============================================================================


class TestPromoteRulesRun:
    """Tests for run_promote_rules main function."""

    def test_run_promote_rules_no_log_files(self, tmp_path, capsys):
        """Test run_promote_rules with no log files."""
        from src.automation.promote_rules import run_promote_rules

        with patch(
            "src.automation.promote_rules.get_review_logs_dir", return_value=tmp_path
        ):
            result = run_promote_rules(days=7)

            assert result == []
            captured = capsys.readouterr()
            assert "로그 파일이 없습니다" in captured.out

    def test_run_promote_rules_no_comments(self, tmp_path, capsys):
        """Test run_promote_rules with log files but no meaningful comments."""
        from src.automation.promote_rules import run_promote_rules

        # Create log file with empty comments
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text('{"inspector_comment": ""}\n')

        with (
            patch(
                "src.automation.promote_rules.get_review_logs_dir", return_value=log_dir
            ),
            patch("src.automation.promote_rules.get_output_dir", return_value=tmp_path),
        ):
            result = run_promote_rules(days=30)

            assert result == []
            captured = capsys.readouterr()
            assert "추출된 코멘트가 없습니다" in captured.out

    def test_run_promote_rules_llm_failure(self, tmp_path, capsys):
        """Test run_promote_rules when LLM call fails."""
        from src.automation.promote_rules import run_promote_rules

        # Create log file with valid comments
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text('{"inspector_comment": "날짜 형식을 수정해주세요"}\n')

        with (
            patch(
                "src.automation.promote_rules.get_review_logs_dir", return_value=log_dir
            ),
            patch("src.automation.promote_rules.get_output_dir", return_value=tmp_path),
            patch(
                "src.automation.promote_rules.GeminiModelClient"
            ) as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.generate.return_value = "[생성 실패: API error"
            mock_client_class.return_value = mock_client

            result = run_promote_rules(days=30)

            assert result == []
            captured = capsys.readouterr()
            assert "LLM 호출 실패" in captured.out

    def test_run_promote_rules_success(self, tmp_path, capsys):
        """Test run_promote_rules with successful LLM response."""
        from src.automation.promote_rules import run_promote_rules

        # Create log file with valid comments
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text(
            '{"inspector_comment": "날짜 형식을 YYYY-MM-DD로 통일해주세요"}\n'
        )

        llm_response = json.dumps([{"rule": "날짜 형식 통일", "type_hint": "date"}])

        with (
            patch(
                "src.automation.promote_rules.get_review_logs_dir", return_value=log_dir
            ),
            patch("src.automation.promote_rules.get_output_dir", return_value=tmp_path),
            patch(
                "src.automation.promote_rules.GeminiModelClient"
            ) as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.generate.return_value = llm_response
            mock_client_class.return_value = mock_client

            result = run_promote_rules(days=30)

            assert len(result) == 1
            assert result[0]["rule"] == "날짜 형식 통일"

            # Check output file was created
            output_files = list(tmp_path.glob("promoted_suggestions_*.json"))
            assert len(output_files) == 1

    def test_run_promote_rules_parse_failure(self, tmp_path, capsys):
        """Test run_promote_rules when LLM response parsing fails."""
        from src.automation.promote_rules import run_promote_rules

        # Create log file with valid comments
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text('{"inspector_comment": "테스트 코멘트입니다"}\n')

        with (
            patch(
                "src.automation.promote_rules.get_review_logs_dir", return_value=log_dir
            ),
            patch("src.automation.promote_rules.get_output_dir", return_value=tmp_path),
            patch(
                "src.automation.promote_rules.GeminiModelClient"
            ) as mock_client_class,
        ):
            mock_client = MagicMock()
            mock_client.generate.return_value = "Invalid response without JSON"
            mock_client_class.return_value = mock_client

            result = run_promote_rules(days=30)

            assert result == []
            captured = capsys.readouterr()
            assert "규칙 파싱에 실패" in captured.out


class TestPromoteRulesMain:
    """Tests for the main CLI entrypoint."""

    def test_main_success(self, tmp_path, capsys):
        """Test main function with successful execution."""
        from src.automation import promote_rules

        # Create log file
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text('{"inspector_comment": "테스트 코멘트입니다"}\n')

        llm_response = json.dumps([{"rule": "테스트 규칙", "type_hint": "string"}])

        with (
            patch.object(promote_rules, "get_review_logs_dir", return_value=log_dir),
            patch.object(promote_rules, "get_output_dir", return_value=tmp_path),
            patch.object(promote_rules, "GeminiModelClient") as mock_client_class,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_client = MagicMock()
            mock_client.generate.return_value = llm_response
            mock_client_class.return_value = mock_client

            promote_rules.main()

        assert exc_info.value.code == 0

    def test_main_no_rules(self, tmp_path, capsys):
        """Test main function with no rules found."""
        from src.automation import promote_rules

        with (
            patch.object(promote_rules, "get_review_logs_dir", return_value=tmp_path),
            pytest.raises(SystemExit) as exc_info,
        ):
            promote_rules.main()

        assert exc_info.value.code == 1

    def test_main_environment_error(self, tmp_path, capsys):
        """Test main function with environment error."""
        from src.automation import promote_rules

        # Create log file
        log_dir = tmp_path / "review_logs"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "review_2024-01-01.jsonl"
        log_file.write_text('{"inspector_comment": "테스트 코멘트입니다"}\n')

        with (
            patch.object(promote_rules, "get_review_logs_dir", return_value=log_dir),
            patch.object(
                promote_rules,
                "GeminiModelClient",
                side_effect=EnvironmentError("Missing API key"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            promote_rules.main()

        assert exc_info.value.code == 1


# =============================================================================
# Tests for src/infra/worker.py
# =============================================================================


class TestWorkerData2Neo:
    """Tests for Data2Neo extraction in worker."""

    @pytest.mark.asyncio
    async def test_run_data2neo_extraction_no_extractor(self, monkeypatch):
        """Test _run_data2neo_extraction without extractor falls back."""
        from src.infra import worker

        monkeypatch.setattr(worker, "data2neo_extractor", None)

        async def mock_process_task(task):
            return {"request_id": task.request_id, "ocr_text": "test"}

        monkeypatch.setattr(worker, "_process_task", mock_process_task)

        task = worker.OCRTask(request_id="r1", image_path="test.txt", session_id="s1")
        result = await worker._run_data2neo_extraction(task)

        assert result["request_id"] == "r1"

    @pytest.mark.asyncio
    async def test_run_data2neo_extraction_placeholder_content(
        self, monkeypatch, tmp_path
    ):
        """Test _run_data2neo_extraction with placeholder content."""
        from src.infra import worker

        mock_extractor = MagicMock()
        monkeypatch.setattr(worker, "data2neo_extractor", mock_extractor)

        async def mock_process_task(task):
            return {"request_id": task.request_id, "ocr_text": "test"}

        monkeypatch.setattr(worker, "_process_task", mock_process_task)

        # Non-existent file path will create placeholder content
        task = worker.OCRTask(
            request_id="r2", image_path="nonexistent.png", session_id="s2"
        )
        result = await worker._run_data2neo_extraction(task)

        assert result["request_id"] == "r2"

    @pytest.mark.asyncio
    async def test_run_data2neo_extraction_success(self, monkeypatch, tmp_path):
        """Test _run_data2neo_extraction with successful extraction."""
        from src.infra import worker

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("John works at Acme Corp")

        mock_result = MagicMock()
        mock_result.document_id = "doc_123"
        mock_result.entities = [
            MagicMock(type=MagicMock(value="Person")),
            MagicMock(type=MagicMock(value="Organization")),
        ]
        mock_result.relationships = []
        mock_result.chunk_count = 1

        mock_extractor = MagicMock()
        mock_extractor.extract_and_import = AsyncMock(return_value=mock_result)
        monkeypatch.setattr(worker, "data2neo_extractor", mock_extractor)

        task = worker.OCRTask(
            request_id="r3", image_path=str(test_file), session_id="s3"
        )
        result = await worker._run_data2neo_extraction(task)

        assert result["request_id"] == "r3"
        assert "data2neo" in result
        assert result["data2neo"]["document_id"] == "doc_123"
        assert result["data2neo"]["entity_count"] == 2

    @pytest.mark.asyncio
    async def test_run_data2neo_extraction_error(self, monkeypatch, tmp_path):
        """Test _run_data2neo_extraction handles extraction error."""
        from src.infra import worker

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Some real content")

        mock_extractor = MagicMock()
        mock_extractor.extract_and_import = AsyncMock(
            side_effect=Exception("Extraction failed")
        )
        monkeypatch.setattr(worker, "data2neo_extractor", mock_extractor)

        async def mock_process_task(task):
            return {"request_id": task.request_id, "ocr_text": "fallback"}

        monkeypatch.setattr(worker, "_process_task", mock_process_task)

        task = worker.OCRTask(
            request_id="r4", image_path=str(test_file), session_id="s4"
        )
        result = await worker._run_data2neo_extraction(task)

        # Should fall back to basic processing
        assert result["request_id"] == "r4"
        assert result["ocr_text"] == "fallback"


class TestWorkerRedis:
    """Tests for Redis-related worker functions."""

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_no_client(self, monkeypatch):
        """Test ensure_redis_ready without redis client."""
        from src.infra import worker

        monkeypatch.setattr(worker, "redis_client", None)

        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await worker.ensure_redis_ready()

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_ping_fails(self, monkeypatch):
        """Test ensure_redis_ready when ping returns False."""
        from src.infra import worker

        class MockRedis:
            async def ping(self):
                return False

        monkeypatch.setattr(worker, "redis_client", MockRedis())

        with pytest.raises(RuntimeError, match="Redis ping failed"):
            await worker.ensure_redis_ready()


class TestWorkerHandleOcrTask:
    """Tests for handle_ocr_task edge cases."""

    @pytest.mark.asyncio
    async def test_handle_ocr_task_data2neo_toggle(self, monkeypatch):
        """Test handle_ocr_task with Data2Neo enabled."""
        from src.infra import worker

        async def mock_ready():
            pass

        monkeypatch.setattr(worker, "ensure_redis_ready", mock_ready)

        async def mock_rate_limit(*args, **kwargs):
            return True

        monkeypatch.setattr(worker, "check_rate_limit", mock_rate_limit)
        monkeypatch.setattr(worker.config, "enable_data2neo", True, raising=False)
        monkeypatch.setattr(worker.config, "enable_lats", False, raising=False)

        async def mock_data2neo(task):
            return {
                "request_id": task.request_id,
                "data2neo": {"document_id": "doc_1"},
            }

        monkeypatch.setattr(worker, "_run_data2neo_extraction", mock_data2neo)

        written = []
        monkeypatch.setattr(worker, "_append_jsonl", lambda p, rec: written.append(rec))

        class MockBroker:
            published = []

            async def publish(self, msg, channel):
                self.published.append((channel, msg))

        broker = MockBroker()
        monkeypatch.setattr(worker, "broker", broker)

        task = worker.OCRTask(request_id="d1", image_path="img", session_id="s1")
        await worker.handle_ocr_task(task)

        assert len(written) == 1
        assert written[0]["request_id"] == "d1"

    @pytest.mark.asyncio
    async def test_handle_ocr_task_redis_not_ready(self, monkeypatch):
        """Test handle_ocr_task continues when Redis not ready."""
        from src.infra import worker

        async def mock_ready_fails():
            raise RuntimeError("Redis not available")

        monkeypatch.setattr(worker, "ensure_redis_ready", mock_ready_fails)

        async def mock_rate_limit(*args, **kwargs):
            return True

        monkeypatch.setattr(worker, "check_rate_limit", mock_rate_limit)
        monkeypatch.setattr(worker.config, "enable_data2neo", False, raising=False)
        monkeypatch.setattr(worker.config, "enable_lats", False, raising=False)

        async def mock_process(task):
            return {"request_id": task.request_id, "ocr_text": "test"}

        monkeypatch.setattr(worker, "_process_task", mock_process)

        written = []
        monkeypatch.setattr(worker, "_append_jsonl", lambda p, rec: written.append(rec))

        class MockBroker:
            published = []

            async def publish(self, msg, channel):
                self.published.append((channel, msg))

        broker = MockBroker()
        monkeypatch.setattr(worker, "broker", broker)

        task = worker.OCRTask(request_id="r1", image_path="img", session_id="s1")
        await worker.handle_ocr_task(task)

        assert len(written) == 1


# =============================================================================
# Tests for src/main.py
# =============================================================================


class TestMainEntryPoint:
    """Tests for main.py entry point."""

    @pytest.mark.asyncio
    async def test_main_value_error(self, monkeypatch, tmp_path):
        """Test main handles ValueError during initialization."""
        import src.main as main_module

        template_dir = tmp_path / "templates"
        template_dir.mkdir(parents=True)

        def raise_value_error():
            raise ValueError("Invalid configuration")

        monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
        monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
        monkeypatch.setattr(
            main_module,
            "setup_logging",
            lambda log_level=None: (MagicMock(), SimpleNamespace(stop=lambda: None)),
        )
        monkeypatch.setattr(main_module, "AppConfig", raise_value_error)

        with pytest.raises(SystemExit) as exc_info:
            await main_module.main()

        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_main_file_not_found(self, monkeypatch, tmp_path):
        """Test main handles FileNotFoundError during initialization."""
        import src.main as main_module

        # Create a config that points to non-existent template_dir
        class FakeConfig:
            def __init__(self):
                self.api_key = "AIza" + "0" * 35
                self.template_dir = tmp_path / "nonexistent_templates"
                self.input_dir = tmp_path / "inputs"
                self.output_dir = tmp_path / "outputs"

        monkeypatch.setenv("LOG_FILE", str(tmp_path / "app.log"))
        monkeypatch.setenv("ERROR_LOG_FILE", str(tmp_path / "error.log"))
        monkeypatch.setattr(
            main_module,
            "setup_logging",
            lambda log_level=None: (MagicMock(), SimpleNamespace(stop=lambda: None)),
        )
        monkeypatch.setattr(main_module, "AppConfig", FakeConfig)
        monkeypatch.setattr(main_module.genai, "configure", lambda api_key: None)

        with pytest.raises(SystemExit) as exc_info:
            await main_module.main()

        assert exc_info.value.code == 1


# =============================================================================
# Tests for src/graph/data2neo_extractor.py
# =============================================================================


class TestGraphData2NeoExtractor:
    """Tests for graph/data2neo_extractor.py."""

    @pytest.fixture
    def mock_templates(self):
        """Create mock Jinja2 templates."""
        from jinja2 import DictLoader

        return DictLoader(
            {
                "prompt_entity_extraction.j2": "Extract: {{ response_schema }}",
                "entity_extraction_user.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def mock_agent(self):
        """Create mock GeminiAgent."""
        agent = MagicMock()
        agent._create_generative_model = MagicMock(return_value=MagicMock())
        agent._call_api_with_retry = AsyncMock()
        return agent

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock AppConfig."""
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100
        return config

    @pytest.mark.asyncio
    async def test_extract_entities_api_error(
        self, mock_config, mock_agent, mock_templates
    ):
        """Test extract_entities handles API errors."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor

        mock_agent._call_api_with_retry.side_effect = Exception("API Error")

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            jinja_env=jinja_env,
        )

        with pytest.raises(Exception, match="API Error"):
            await extractor.extract_entities("Test OCR text")

    @pytest.mark.asyncio
    async def test_write_to_graph_with_dates(
        self, mock_config, mock_agent, mock_templates
    ):
        """Test write_to_graph writes date entities."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor
        from src.graph.entities import DateEntity, ExtractionResult

        mock_graph_provider = AsyncMock()
        mock_graph_provider.create_nodes = AsyncMock(return_value=1)
        mock_graph_provider.create_relationships = AsyncMock(return_value=1)

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            graph_provider=mock_graph_provider,
            jinja_env=jinja_env,
        )

        result = ExtractionResult(
            dates=[
                DateEntity(
                    name="January 15, 2024",
                    confidence=0.9,
                    normalized="2024-01-15",
                )
            ]
        )

        counts = await extractor.write_to_graph(result)

        assert counts["dates"] == 1
        mock_graph_provider.create_nodes.assert_called()

    @pytest.mark.asyncio
    async def test_write_to_graph_with_document_rules(
        self, mock_config, mock_agent, mock_templates
    ):
        """Test write_to_graph writes document rule entities."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor
        from src.graph.entities import DocumentRule, ExtractionResult

        mock_graph_provider = AsyncMock()
        mock_graph_provider.create_nodes = AsyncMock(return_value=1)
        mock_graph_provider.create_relationships = AsyncMock(return_value=1)

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            graph_provider=mock_graph_provider,
            jinja_env=jinja_env,
        )

        result = ExtractionResult(
            document_rules=[
                DocumentRule(
                    name="All documents must be reviewed",
                    confidence=0.85,
                    priority="high",
                )
            ]
        )

        counts = await extractor.write_to_graph(result)

        assert counts["document_rules"] == 1

    @pytest.mark.asyncio
    async def test_write_to_graph_relationship_error(
        self, mock_config, mock_agent, mock_templates
    ):
        """Test write_to_graph handles relationship creation errors."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor
        from src.graph.entities import ExtractionResult, Person, Relationship

        mock_graph_provider = AsyncMock()
        mock_graph_provider.create_nodes = AsyncMock(return_value=1)
        mock_graph_provider.create_relationships = AsyncMock(
            side_effect=Exception("Relationship error")
        )

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            graph_provider=mock_graph_provider,
            jinja_env=jinja_env,
        )

        result = ExtractionResult(
            persons=[Person(name="John", confidence=0.9)],
            relationships=[
                Relationship(
                    from_entity="John",
                    to_entity="Acme",
                    rel_type="WORKS_AT",
                )
            ],
        )

        # Should not raise, just log warning
        counts = await extractor.write_to_graph(result)

        assert counts["persons"] == 1
        assert counts["relationships"] == 0  # Failed to create

    def test_parse_partial_result(self, mock_config, mock_agent, mock_templates):
        """Test _parse_partial_result handles malformed data."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            jinja_env=jinja_env,
        )

        # Data with some valid and some invalid entries
        data = {
            "persons": [
                {"name": "Valid Person", "confidence": 0.9},
                {"invalid": "no name field"},  # Invalid
            ],
            "organizations": [
                {"name": "Valid Org", "confidence": 0.85},
            ],
            "dates": [
                {"invalid": "date"},  # Invalid
            ],
            "document_rules": [
                {"name": "Valid Rule", "confidence": 0.8},
            ],
            "relationships": [
                {
                    "from_entity": "A",
                    "to_entity": "B",
                    "rel_type": "REL",
                },
                {"invalid": "relationship"},  # Invalid
            ],
        }

        result = extractor._parse_partial_result(data)

        assert len(result.persons) == 1
        assert len(result.organizations) == 1
        assert len(result.dates) == 0
        assert len(result.document_rules) == 1
        assert len(result.relationships) == 1


# =============================================================================
# Tests for src/workflow/executor.py
# =============================================================================


class TestWorkflowExecutor:
    """Tests for workflow executor."""

    @pytest.mark.asyncio
    async def test_load_checkpoint_records_no_resume(self):
        """Test _load_checkpoint_records returns empty when resume is False."""
        from src.workflow.executor import _load_checkpoint_records

        logger = MagicMock()
        result = await _load_checkpoint_records(
            Path("/tmp/checkpoint.jsonl"), resume=False, logger=logger
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_checkpoint_records_with_resume(self, tmp_path):
        """Test _load_checkpoint_records loads records when resume is True."""
        from src.workflow.executor import _load_checkpoint_records

        # Create checkpoint file
        checkpoint_path = tmp_path / "checkpoint.jsonl"
        checkpoint_path.write_text(
            '{"query": "Q1", "success": true}\n{"query": "Q2", "success": true}\n'
        )

        logger = MagicMock()

        with patch("src.workflow.executor.load_checkpoint") as mock_load:
            mock_load.return_value = {"Q1": MagicMock(), "Q2": MagicMock()}

            result = await _load_checkpoint_records(
                checkpoint_path, resume=True, logger=logger
            )

            assert len(result) == 2
            logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_load_candidates_auto_mode(self, tmp_path):
        """Test _load_candidates in AUTO mode."""
        from src.workflow.executor import _load_candidates
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.input_dir = tmp_path
        logger = MagicMock()

        with patch(
            "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
        ) as mock_reload:
            mock_reload.return_value = ("ocr", {"A": "a", "B": "b"})

            result = await _load_candidates(
                config=config,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                is_interactive=False,
                logger=logger,
            )

            assert result == {"A": "a", "B": "b"}
            logger.info.assert_any_call("AUTO 모드: 데이터 자동 로딩 중...")

    @pytest.mark.asyncio
    async def test_load_candidates_interactive_skip_reload(self, tmp_path):
        """Test _load_candidates when user skips reload."""
        from src.workflow.executor import _load_candidates
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.input_dir = tmp_path
        logger = MagicMock()

        with (
            patch("src.workflow.executor.Confirm.ask", return_value=False),
            patch(
                "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
            ) as mock_reload,
        ):
            mock_reload.return_value = ("ocr", {"A": "a"})

            result = await _load_candidates(
                config=config,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                is_interactive=True,
                logger=logger,
            )

            assert result == {"A": "a"}
            logger.info.assert_any_call("재로딩 없이 진행")

    @pytest.mark.asyncio
    async def test_load_candidates_interactive_reload_error(self, tmp_path):
        """Test _load_candidates handles reload error."""
        from src.workflow.executor import _load_candidates
        from src.config import AppConfig
        from src.config.exceptions import ValidationFailedError

        config = MagicMock(spec=AppConfig)
        config.input_dir = tmp_path
        logger = MagicMock()

        with (
            patch("src.workflow.executor.Confirm.ask", return_value=True),
            patch(
                "src.workflow.executor.reload_data_if_needed",
                side_effect=ValidationFailedError("Invalid data"),
            ),
        ):
            result = await _load_candidates(
                config=config,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                is_interactive=True,
                logger=logger,
            )

            assert result is None
            logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_create_context_cache_error(self):
        """Test _create_context_cache handles errors."""
        from src.workflow.executor import _create_context_cache
        from src.config.exceptions import CacheCreationError

        mock_agent = MagicMock()
        mock_agent.create_context_cache = AsyncMock(
            side_effect=CacheCreationError("Cache error")
        )
        logger = MagicMock()

        result = await _create_context_cache(mock_agent, "OCR text", logger)

        assert result is None
        logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_gather_results_handles_exceptions(self):
        """Test _gather_results handles and logs exceptions."""
        from src.workflow.executor import _gather_results

        async def raise_error():
            raise ValueError("Task failed")

        logger = MagicMock()
        tasks = [asyncio.create_task(raise_error())]

        with pytest.raises(ValueError, match="Task failed"):
            await _gather_results(tasks, logger)

        logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_gather_results_filters_none(self):
        """Test _gather_results filters out None results."""
        from src.workflow.executor import _gather_results
        from src.core.models import (
            WorkflowResult,
            EvaluationResultSchema,
            EvaluationItem,
        )

        async def return_none():
            return None

        async def return_result():
            eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
            evaluation = EvaluationResultSchema(
                best_candidate="A", evaluations=[eval_item]
            )
            return WorkflowResult(
                turn_id=1,
                query="Q",
                evaluation=evaluation,
                best_candidate="A",
                best_answer="answer",
                rewritten_answer="rewritten",
            )

        logger = MagicMock()
        tasks = [
            asyncio.create_task(return_none()),
            asyncio.create_task(return_result()),
        ]

        results = await _gather_results(tasks, logger)

        assert len(results) == 1
        assert results[0].query == "Q"

    def test_resolve_checkpoint_path_default(self, tmp_path):
        """Test _resolve_checkpoint_path uses default path."""
        from src.workflow.executor import _resolve_checkpoint_path
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.output_dir = tmp_path

        result = _resolve_checkpoint_path(config, None)

        assert result == tmp_path / "checkpoint.jsonl"

    def test_resolve_checkpoint_path_relative(self, tmp_path):
        """Test _resolve_checkpoint_path handles relative path."""
        from src.workflow.executor import _resolve_checkpoint_path
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.output_dir = tmp_path

        result = _resolve_checkpoint_path(config, Path("custom.jsonl"))

        assert result == tmp_path / "custom.jsonl"

    @pytest.mark.asyncio
    async def test_execute_workflow_cache_cleanup_error(self):
        """Test execute_workflow handles cache cleanup errors."""
        from src.workflow.executor import execute_workflow
        from src.core.models import EvaluationItem, EvaluationResultSchema

        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
        mock_agent.check_budget = MagicMock(return_value=None)
        mock_agent.get_budget_usage_percent = MagicMock(return_value=10.0)

        mock_cache = MagicMock()
        mock_cache.delete.side_effect = OSError("Cannot delete cache")
        mock_cache.name = "test_cache"
        mock_agent.create_context_cache = AsyncMock(return_value=mock_cache)

        eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
        eval_result = EvaluationResultSchema(
            best_candidate="A", evaluations=[eval_item]
        )
        mock_agent.evaluate_responses = AsyncMock(return_value=eval_result)
        mock_agent.rewrite_best_answer = AsyncMock(return_value="Rewritten")

        logger = MagicMock()

        with (
            patch(
                "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
            ) as mock_reload,
            patch("src.workflow.processor.save_result_to_file"),
        ):
            mock_reload.return_value = ("ocr", {"A": "a"})

            results = await execute_workflow(
                agent=mock_agent,
                ocr_text="ocr",
                user_intent=None,
                logger=logger,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                is_interactive=False,
            )

            # Should complete successfully despite cache cleanup error
            assert len(results) == 1
            logger.warning.assert_any_call("Cache cleanup failed: %s", ANY)

    @pytest.mark.asyncio
    async def test_execute_workflow_simple(self, tmp_path):
        """Test execute_workflow_simple."""
        from src.workflow.executor import execute_workflow_simple
        from src.config import AppConfig
        from src.core.models import EvaluationItem, EvaluationResultSchema

        config = MagicMock(spec=AppConfig)
        config.output_dir = tmp_path

        mock_agent = MagicMock()
        mock_agent.create_context_cache = AsyncMock(return_value=None)

        eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
        eval_result = EvaluationResultSchema(
            best_candidate="A", evaluations=[eval_item]
        )
        mock_agent.evaluate_responses = AsyncMock(return_value=eval_result)
        mock_agent.rewrite_best_answer = AsyncMock(return_value="Rewritten")

        logger = MagicMock()

        with patch("src.workflow.processor.save_result_to_file"):
            result = await execute_workflow_simple(
                agent=mock_agent,
                ocr_text="ocr",
                candidates={"A": "answer A"},
                config=config,
                logger=logger,
                query="Test query",
                turn_id=1,
            )

            assert result is not None
            assert result.query == "Test query"


# =============================================================================
# Additional tests for src/analysis/__init__.py
# =============================================================================


class TestAnalysisInit:
    """Tests for analysis package __init__.py."""

    def test_getattr_cross_validation_system(self):
        """Test lazy loading of CrossValidationSystem."""
        from src import analysis

        # This should trigger the __getattr__ mechanism
        CrossValidationSystem = analysis.CrossValidationSystem
        assert CrossValidationSystem is not None
        # Verify it's the correct class
        from src.analysis.cross_validation import (
            CrossValidationSystem as DirectImport,
        )

        assert CrossValidationSystem is DirectImport

    def test_getattr_invalid_attribute(self):
        """Test __getattr__ raises AttributeError for unknown attribute."""
        from src import analysis

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = analysis.NonExistentClass


# =============================================================================
# Additional tests for src/infra/utils.py
# =============================================================================


class TestInfraUtils:
    """Additional tests for infra utilities."""

    def test_find_in_nested_list(self):
        """Test _find_in_nested with list structures."""
        from src.infra.utils import _find_in_nested

        obj = [{"level1": [{"level2": {"target": "found"}}]}]
        result = _find_in_nested(obj, "target")
        assert result == "found"

    def test_find_in_nested_not_found(self):
        """Test _find_in_nested when key not found."""
        from src.infra.utils import _find_in_nested

        obj = {"a": {"b": {"c": 1}}}
        result = _find_in_nested(obj, "nonexistent")
        assert result is None

    def test_safe_json_parse_with_raise(self):
        """Test safe_json_parse with raise_on_error=True."""
        from src.infra.utils import safe_json_parse

        with pytest.raises(Exception):
            safe_json_parse("invalid json {", raise_on_error=True)

    def test_safe_json_parse_target_key(self):
        """Test safe_json_parse with target_key extraction."""
        from src.infra.utils import safe_json_parse

        text = '{"outer": {"inner": {"target": "value"}}}'
        result = safe_json_parse(text, target_key="target")
        assert result == "value"

    def test_clean_markdown_code_block(self):
        """Test clean_markdown_code_block function."""
        from src.infra.utils import clean_markdown_code_block

        # Test with markdown code block
        text = '```json\n{"key": "value"}\n```'
        result = clean_markdown_code_block(text)
        assert result == '{"key": "value"}'

        # Test without markdown code block
        text2 = '{"key": "value"}'
        result2 = clean_markdown_code_block(text2)
        assert result2 == '{"key": "value"}'


# =============================================================================
# Additional tests for src/workflow/executor.py
# =============================================================================


class TestWorkflowExecutorAdditional:
    """Additional tests for workflow executor."""

    def test_warn_budget_thresholds_at_threshold(self):
        """Test _warn_budget_thresholds emits warnings at 80% threshold."""
        from src.workflow.executor import _warn_budget_thresholds

        # Create a simple object that can have attributes added
        class MockAgent:
            def get_budget_usage_percent(self):
                return 80.0

        mock_agent = MockAgent()
        logger = MagicMock()

        # First call should emit warning
        _warn_budget_thresholds(mock_agent, logger)

        # Should have logged warning for 80% threshold
        assert logger.warning.call_count == 1

        # Verify the attribute was set
        assert hasattr(mock_agent, "_warned_80")

        # Second call should not emit again (already warned)
        _warn_budget_thresholds(mock_agent, logger)
        assert logger.warning.call_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_load_candidates_interactive_reload(self, tmp_path):
        """Test _load_candidates when user requests reload."""
        from src.workflow.executor import _load_candidates
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.input_dir = tmp_path
        logger = MagicMock()

        with (
            patch("src.workflow.executor.Confirm.ask", return_value=True),
            patch(
                "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
            ) as mock_reload,
        ):
            mock_reload.return_value = ("ocr", {"A": "a", "B": "b"})

            result = await _load_candidates(
                config=config,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                is_interactive=True,
                logger=logger,
            )

            assert result == {"A": "a", "B": "b"}
            logger.info.assert_any_call("사용자 요청으로 데이터 재로딩 중...")


# =============================================================================
# Additional tests for src/graph/data2neo_extractor.py
# =============================================================================


class TestGraphData2NeoExtractorAdditional:
    """Additional tests for graph data2neo extractor."""

    @pytest.fixture
    def mock_templates(self):
        """Create mock Jinja2 templates."""
        from jinja2 import DictLoader

        return DictLoader(
            {
                "prompt_entity_extraction.j2": "Extract: {{ response_schema }}",
                "entity_extraction_user.j2": "Text: {{ ocr_text }}",
            }
        )

    @pytest.fixture
    def mock_agent(self):
        """Create mock GeminiAgent."""
        agent = MagicMock()
        agent._create_generative_model = MagicMock(return_value=MagicMock())
        agent._call_api_with_retry = AsyncMock()
        return agent

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock AppConfig."""
        from src.config import AppConfig

        config = MagicMock(spec=AppConfig)
        config.template_dir = tmp_path
        config.data2neo_confidence = 0.7
        config.data2neo_batch_size = 100
        return config

    @pytest.mark.asyncio
    async def test_write_to_graph_all_entity_types(
        self, mock_config, mock_agent, mock_templates
    ):
        """Test write_to_graph with all entity types."""
        from jinja2 import Environment

        from src.graph.data2neo_extractor import Data2NeoExtractor
        from src.graph.entities import (
            DateEntity,
            DocumentRule,
            ExtractionResult,
            Organization,
            Person,
            Relationship,
        )

        mock_graph_provider = AsyncMock()
        mock_graph_provider.create_nodes = AsyncMock(return_value=1)
        mock_graph_provider.create_relationships = AsyncMock(return_value=1)

        jinja_env = Environment(loader=mock_templates)
        extractor = Data2NeoExtractor(
            config=mock_config,
            agent=mock_agent,
            graph_provider=mock_graph_provider,
            jinja_env=jinja_env,
        )

        result = ExtractionResult(
            persons=[Person(name="John", confidence=0.9)],
            organizations=[Organization(name="Acme", confidence=0.85)],
            dates=[DateEntity(name="2024-01-15", confidence=0.8)],
            document_rules=[DocumentRule(name="Rule 1", confidence=0.75)],
            relationships=[
                Relationship(
                    from_entity="John",
                    to_entity="Acme",
                    rel_type="WORKS_AT",
                )
            ],
        )

        counts = await extractor.write_to_graph(result)

        assert counts["persons"] == 1
        assert counts["organizations"] == 1
        assert counts["dates"] == 1
        assert counts["document_rules"] == 1
        assert counts["relationships"] == 1
