"""Comprehensive tests for src/infra/worker.py to improve coverage to 80%+."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig
from src.infra.worker import (
    DLQMessage,
    OCRTask,
    SearchState,
    ValidationResult,
    _append_jsonl,
    _process_task,
    _run_data2neo_extraction,
    _run_task_with_lats,
    check_rate_limit,
    ensure_redis_ready,
    get_config,
    handle_ocr_task,
)


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.incr = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    return client


@pytest.fixture
def sample_ocr_task():
    """Sample OCR task for testing."""
    return OCRTask(
        request_id="test_req_001",
        image_path="/tmp/test_image.txt",
        session_id="test_session_001",
    )


@pytest.fixture
def temp_results_dir(tmp_path):
    """Temporary results directory."""
    results_dir = tmp_path / "queue_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


class TestGetConfig:
    """Test get_config function."""

    def test_get_config_creates_instance(self):
        """Test that get_config creates AppConfig instance."""
        import src.infra.worker as worker_module

        worker_module._config = None
        config = get_config()
        assert isinstance(config, AppConfig)
        assert config.gemini_api_key is not None

    def test_get_config_reuses_instance(self):
        """Test that get_config reuses existing instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


class TestOCRTask:
    """Test OCRTask model."""

    def test_ocr_task_creation(self, sample_ocr_task):
        """Test OCRTask creation with required fields."""
        assert sample_ocr_task.request_id == "test_req_001"
        assert sample_ocr_task.image_path == "/tmp/test_image.txt"
        assert sample_ocr_task.session_id == "test_session_001"

    def test_ocr_task_model_dump(self, sample_ocr_task):
        """Test OCRTask serialization."""
        data = sample_ocr_task.model_dump()
        assert data["request_id"] == "test_req_001"
        assert data["image_path"] == "/tmp/test_image.txt"
        assert data["session_id"] == "test_session_001"


class TestDLQMessage:
    """Test DLQMessage model."""

    def test_dlq_message_creation(self):
        """Test DLQMessage creation."""
        msg = DLQMessage(
            request_id="req_123",
            error_type="TestError",
            payload={"key": "value"},
        )
        assert msg.request_id == "req_123"
        assert msg.error_type == "TestError"
        assert msg.payload == {"key": "value"}
        assert msg.timestamp is not None

    def test_dlq_message_auto_timestamp(self):
        """Test DLQMessage auto-generates timestamp."""
        msg = DLQMessage(
            request_id="req_123",
            error_type="TestError",
            payload={},
        )
        # Parse timestamp to ensure it's valid ISO format
        ts = datetime.fromisoformat(msg.timestamp)
        assert ts.tzinfo is not None  # Has timezone
        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        diff = (now - ts).total_seconds()
        assert diff < 60


class TestAppendJsonl:
    """Test _append_jsonl helper function."""

    def test_append_jsonl_creates_parent_dir(self, tmp_path):
        """Test that _append_jsonl creates parent directories."""
        file_path = tmp_path / "subdir" / "results.jsonl"
        record = {"test": "data", "value": 123}

        _append_jsonl(file_path, record)

        assert file_path.exists()
        assert file_path.parent.exists()

    def test_append_jsonl_writes_valid_json(self, tmp_path):
        """Test that _append_jsonl writes valid JSON lines."""
        file_path = tmp_path / "results.jsonl"
        record1 = {"id": 1, "value": "first"}
        record2 = {"id": 2, "value": "second"}

        _append_jsonl(file_path, record1)
        _append_jsonl(file_path, record2)

        lines = file_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == record1
        assert json.loads(lines[1]) == record2

    def test_append_jsonl_handles_unicode(self, tmp_path):
        """Test that _append_jsonl handles Unicode correctly."""
        file_path = tmp_path / "results.jsonl"
        record = {"text": "한글 테스트", "emoji": "🎉"}

        _append_jsonl(file_path, record)

        content = file_path.read_text(encoding="utf-8")
        loaded = json.loads(content.strip())
        assert loaded["text"] == "한글 테스트"
        assert loaded["emoji"] == "🎉"


class TestCheckRateLimit:
    """Test check_rate_limit function."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_allows_first_request(self, mock_redis_client):
        """Test that first request is allowed."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client
        mock_redis_client.incr.return_value = 1

        allowed = await check_rate_limit("test_key", limit=10, window=60)

        assert allowed is True
        mock_redis_client.incr.assert_called_once_with("test_key")
        mock_redis_client.expire.assert_called_once_with("test_key", 60)

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocks_when_exceeded(self, mock_redis_client):
        """Test that requests are blocked when limit exceeded."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client
        mock_redis_client.incr.return_value = 11  # Over limit of 10

        allowed = await check_rate_limit("test_key", limit=10, window=60)

        assert allowed is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_without_redis(self):
        """Test that check_rate_limit fails open when Redis unavailable."""
        import src.infra.worker as worker_module

        worker_module.redis_client = None

        allowed = await check_rate_limit("test_key", limit=10, window=60)

        assert allowed is True  # Fails open

    @pytest.mark.asyncio
    async def test_check_rate_limit_sets_expiry_only_once(self, mock_redis_client):
        """Test that expiry is set only on first increment."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client
        mock_redis_client.incr.return_value = 5  # Not first request

        await check_rate_limit("test_key", limit=10, window=60)

        mock_redis_client.expire.assert_not_called()


class TestEnsureRedisReady:
    """Test ensure_redis_ready function."""

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_success(self, mock_redis_client):
        """Test successful Redis ping."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client

        await ensure_redis_ready()  # Should not raise

        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_fails_when_not_initialized(self):
        """Test failure when Redis client not initialized."""
        import src.infra.worker as worker_module

        worker_module.redis_client = None

        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await ensure_redis_ready()

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_fails_when_ping_fails(self, mock_redis_client):
        """Test failure when Redis ping returns False."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client
        mock_redis_client.ping.return_value = False

        with pytest.raises(RuntimeError, match="Redis ping failed"):
            await ensure_redis_ready()

    @pytest.mark.asyncio
    async def test_ensure_redis_ready_handles_exception(self, mock_redis_client):
        """Test exception handling in ensure_redis_ready."""
        import src.infra.worker as worker_module

        worker_module.redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Connection error")

        with pytest.raises(Exception):
            await ensure_redis_ready()


class TestProcessTask:
    """Test _process_task function."""

    @pytest.mark.asyncio
    async def test_process_task_reads_txt_file(self, tmp_path, sample_ocr_task):
        """Test processing task with existing .txt file."""
        import src.infra.worker as worker_module

        # Create test file
        test_file = tmp_path / "test_image.txt"
        test_file.write_text("Sample OCR text content", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )
        worker_module.llm_provider = None  # No LLM processing

        result = await _process_task(task)

        assert result["request_id"] == "req_001"
        assert result["session_id"] == "session_001"
        assert result["ocr_text"] == "Sample OCR text content"
        assert result["llm_output"] is None
        assert "processed_at" in result

    @pytest.mark.asyncio
    async def test_process_task_uses_placeholder_for_non_txt(self, sample_ocr_task):
        """Test processing task with non-.txt file."""
        import src.infra.worker as worker_module

        task = OCRTask(
            request_id="req_001",
            image_path="/path/to/image.png",
            session_id="session_001",
        )
        worker_module.llm_provider = None

        result = await _process_task(task)

        assert "OCR placeholder for image.png" in result["ocr_text"]
        assert result["llm_output"] is None

    @pytest.mark.asyncio
    async def test_process_task_handles_read_error(self, tmp_path):
        """Test processing task handles file read errors."""
        import src.infra.worker as worker_module

        # Create file with no read permissions
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        test_file.chmod(0o000)  # Remove all permissions

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )
        worker_module.llm_provider = None

        result = await _process_task(task)

        # Should use placeholder when read fails
        assert "OCR placeholder" in result["ocr_text"]

        # Cleanup
        test_file.chmod(0o644)

    @pytest.mark.asyncio
    async def test_process_task_with_llm_provider(self, tmp_path):
        """Test processing task with LLM provider."""
        import src.infra.worker as worker_module

        test_file = tmp_path / "test.txt"
        test_file.write_text("Raw OCR text", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )

        # Mock LLM provider
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Cleaned OCR text"
        mock_llm.generate_content_async.return_value = mock_response
        worker_module.llm_provider = mock_llm

        result = await _process_task(task)

        assert result["ocr_text"] == "Raw OCR text"
        assert result["llm_output"] == "Cleaned OCR text"
        mock_llm.generate_content_async.assert_called_once()


class TestRunData2NeoExtraction:
    """Test _run_data2neo_extraction function."""

    @pytest.mark.asyncio
    async def test_run_data2neo_without_extractor(self, tmp_path):
        """Test data2neo extraction falls back when extractor unavailable."""
        import src.infra.worker as worker_module

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )

        worker_module.data2neo_extractor = None
        worker_module.llm_provider = None

        result = await _run_data2neo_extraction(task)

        # Should fall back to basic _process_task
        assert result["ocr_text"] == "Test content"
        assert "data2neo" not in result

    @pytest.mark.asyncio
    async def test_run_data2neo_with_placeholder_content(self):
        """Test data2neo extraction skips placeholder content."""
        import src.infra.worker as worker_module

        task = OCRTask(
            request_id="req_001",
            image_path="/path/to/nonexistent.png",
            session_id="session_001",
        )

        mock_extractor = AsyncMock()
        worker_module.data2neo_extractor = mock_extractor
        worker_module.llm_provider = None

        result = await _run_data2neo_extraction(task)

        # Should skip extraction for placeholder content
        assert "OCR placeholder" in result["ocr_text"]
        assert "data2neo" not in result
        mock_extractor.extract_and_import.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_data2neo_successful_extraction(self, tmp_path):
        """Test successful data2neo extraction."""
        import src.infra.worker as worker_module

        test_file = tmp_path / "test.txt"
        test_file.write_text("Company XYZ reported revenue of $1M", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )

        # Mock extractor
        mock_extractor = AsyncMock()
        mock_result = MagicMock()
        mock_result.document_id = "doc_123"
        mock_result.entities = [
            MagicMock(type=MagicMock(value="Organization")),
            MagicMock(type=MagicMock(value="Organization")),
        ]
        mock_result.relationships = [MagicMock()]
        mock_result.chunk_count = 1
        mock_extractor.extract_and_import.return_value = mock_result

        worker_module.data2neo_extractor = mock_extractor

        result = await _run_data2neo_extraction(task)

        assert result["request_id"] == "req_001"
        assert "data2neo" in result
        assert result["data2neo"]["document_id"] == "doc_123"
        assert result["data2neo"]["entity_count"] == 2
        assert result["data2neo"]["relationship_count"] == 1
        assert result["data2neo"]["entity_types"]["Organization"] == 2

    @pytest.mark.asyncio
    async def test_run_data2neo_handles_extraction_failure(self, tmp_path):
        """Test data2neo extraction handles failures gracefully."""
        import src.infra.worker as worker_module

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )

        mock_extractor = AsyncMock()
        mock_extractor.extract_and_import.side_effect = Exception("Extraction failed")
        worker_module.data2neo_extractor = mock_extractor
        worker_module.llm_provider = None

        result = await _run_data2neo_extraction(task)

        # Should fall back to basic processing
        assert result["ocr_text"] == "Test content"
        assert "data2neo" not in result


class TestHandleOCRTask:
    """Test handle_ocr_task function."""

    @pytest.mark.asyncio
    async def test_handle_ocr_task_rate_limit_check(self, mock_redis_client):
        """Test handle_ocr_task performs rate limiting."""
        import src.infra.worker as worker_module
        from src.core.interfaces import RateLimitError

        worker_module.redis_client = mock_redis_client
        mock_redis_client.ping.return_value = True
        mock_redis_client.incr.return_value = 11  # Exceeds limit

        task = OCRTask(
            request_id="req_001",
            image_path="/test.txt",
            session_id="session_001",
        )

        with pytest.raises(RateLimitError, match="Global rate limit exceeded"):
            await handle_ocr_task(task)

    @pytest.mark.asyncio
    async def test_handle_ocr_task_continues_without_redis(self, tmp_path):
        """Test handle_ocr_task continues when Redis unavailable."""
        import src.infra.worker as worker_module

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content", encoding="utf-8")

        task = OCRTask(
            request_id="req_001",
            image_path=str(test_file),
            session_id="session_001",
        )

        worker_module.redis_client = None
        worker_module.llm_provider = None
        worker_module.data2neo_extractor = None

        # Mock config
        mock_config = MagicMock()
        mock_config.enable_data2neo = False
        mock_config.enable_lats = False

        with patch("src.infra.worker.get_config", return_value=mock_config):
            with patch("src.infra.worker._append_jsonl") as mock_append:
                # Should not raise
                await handle_ocr_task(task)
                mock_append.assert_called_once()
