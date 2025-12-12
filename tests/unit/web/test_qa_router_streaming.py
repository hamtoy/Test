"""Tests for qa.py router streaming functionality.

Covers:
- _sse() helper function
- _resolve_stream_batch_types() function
- Streaming helper functions
- _stream_batch_events() generator
- stream_batch_qa_generation() endpoint
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.web.models import GenerateQARequest
from src.web.routers import qa


class TestSseHelper:
    """Tests for _sse helper function."""

    def test_sse_basic(self) -> None:
        """Test basic SSE event formatting."""
        result = qa._sse("progress", type="test", data={"key": "value"})

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        # Parse the JSON data
        json_str = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_str)

        assert data["event"] == "progress"
        assert data["type"] == "test"
        assert data["data"] == {"key": "value"}

    def test_sse_done_event(self) -> None:
        """Test SSE done event."""
        result = qa._sse("done", success=True, completed=4, total=4)

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["event"] == "done"
        assert data["success"] is True
        assert data["completed"] == 4
        assert data["total"] == 4

    def test_sse_error_event(self) -> None:
        """Test SSE error event."""
        result = qa._sse("error", type="reasoning", error="timeout")

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["event"] == "error"
        assert data["type"] == "reasoning"
        assert data["error"] == "timeout"


class TestResolveStreamBatchTypes:
    """Tests for _resolve_stream_batch_types function."""

    def test_resolve_default_batch_types(self) -> None:
        """Test resolving default batch types."""
        body = GenerateQARequest(mode="batch", ocr_text="test")

        result = qa._resolve_stream_batch_types(body)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_resolve_custom_batch_types(self) -> None:
        """Test resolving custom batch types."""
        body = GenerateQARequest(
            mode="batch",
            ocr_text="test",
            batch_types=["global_explanation", "reasoning"],
        )

        result = qa._resolve_stream_batch_types(body)

        assert result == ["global_explanation", "reasoning"]

    def test_resolve_batch_three_mode(self) -> None:
        """Test resolving batch_three mode with default types."""
        body = GenerateQARequest(mode="batch_three", ocr_text="test")

        result = qa._resolve_stream_batch_types(body)

        # Should use QA_BATCH_TYPES_THREE
        assert isinstance(result, list)


class TestStreamBatchState:
    """Tests for _StreamBatchState dataclass."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = qa._StreamBatchState()

        assert state.completed_queries == []
        assert state.success_count == 0
        assert state.first_answer == ""

    def test_state_modification(self) -> None:
        """Test state can be modified."""
        state = qa._StreamBatchState()

        state.completed_queries.append("query1")
        state.success_count = 1
        state.first_answer = "answer"

        assert len(state.completed_queries) == 1
        assert state.success_count == 1
        assert state.first_answer == "answer"


class TestMaybeStartReasoningTask:
    """Tests for _maybe_start_reasoning_task function."""

    def test_no_reasoning_type(self) -> None:
        """Test when reasoning is not first type."""
        mock_agent = MagicMock()
        remaining = ["target_short", "target_long"]

        task, new_remaining = qa._maybe_start_reasoning_task(
            remaining, mock_agent, "ocr_text"
        )

        assert task is None
        assert new_remaining == ["target_short", "target_long"]

    def test_empty_remaining_types(self) -> None:
        """Test with empty remaining types."""
        mock_agent = MagicMock()

        task, new_remaining = qa._maybe_start_reasoning_task([], mock_agent, "ocr_text")

        assert task is None
        assert new_remaining == []


class TestCreateStreamTasks:
    """Tests for _create_stream_tasks function."""

    def test_create_tasks_empty(self) -> None:
        """Test creating tasks with empty types."""
        mock_agent = MagicMock()

        task_map = qa._create_stream_tasks(
            remaining_types=[],
            agent=mock_agent,
            ocr_text="test",
            completed_queries=[],
            first_answer="",
        )

        assert len(task_map) == 0


class TestStreamBatchQaGeneration:
    """Tests for stream_batch_qa_generation endpoint."""

    @pytest.mark.asyncio
    async def test_stream_batch_invalid_mode(self) -> None:
        """Test error for non-batch mode."""
        body = GenerateQARequest(mode="single", ocr_text="test")

        with pytest.raises(HTTPException) as exc_info:
            await qa.stream_batch_qa_generation(body)

        assert exc_info.value.status_code == 400
        assert "batch" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_batch_no_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test error when agent is not initialized."""
        body = GenerateQARequest(mode="batch", ocr_text="test")

        monkeypatch.setattr(qa, "_get_agent", lambda: None)

        with pytest.raises(HTTPException) as exc_info:
            await qa.stream_batch_qa_generation(body)

        assert exc_info.value.status_code == 500


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports_contains_key_items(self) -> None:
        """Test that __all__ contains key exports."""
        assert "router" in qa.__all__
        assert "set_dependencies" in qa.__all__
        assert "generate_single_qa" in qa.__all__
        assert "stream_batch_qa_generation" in qa.__all__

    def test_set_dependencies_exists(self) -> None:
        """Test that set_dependencies is available."""
        assert hasattr(qa, "set_dependencies")
        assert callable(qa.set_dependencies)
