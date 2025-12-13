"""Additional tests for src/web/routers/qa.py to improve coverage.

Targets:
- Streaming functionality
- SSE event generation
- Task management
- Error handling in streaming
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, AsyncIterator
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from src.web.models import GenerateQARequest
from src.web.routers.qa import (
    _build_task_map,
    _create_stream_tasks,
    _maybe_start_reasoning_task,
    _resolve_stream_batch_types,
    _sse,
    _StreamBatchState,
    _yield_completed_reasoning_task,
    stream_batch_qa_generation,
)


class TestSSEFormatting:
    """Test Server-Sent Events formatting."""

    def test_sse_formats_event_correctly(self) -> None:
        """Test SSE event formatting."""
        result = _sse("progress", type="reasoning", data={"query": "Q"})

        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        assert '"event": "progress"' in result
        assert '"type": "reasoning"' in result

    def test_sse_handles_multiple_payload_fields(self) -> None:
        """Test SSE with multiple payload fields."""
        result = _sse("started", total=4, message="시작")

        assert '"event": "started"' in result
        assert '"total": 4' in result
        assert '"message"' in result


class TestStreamBatchTypes:
    """Test streaming batch type resolution."""

    def test_resolve_stream_batch_types_default(self) -> None:
        """Test default batch types for streaming."""
        body = GenerateQARequest(mode="batch")
        result = _resolve_stream_batch_types(body)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_resolve_stream_batch_types_custom(self) -> None:
        """Test custom batch types."""
        body = GenerateQARequest(mode="batch", batch_types=["explanation", "reasoning"])
        result = _resolve_stream_batch_types(body)
        assert result == ["explanation", "reasoning"]

    def test_resolve_stream_batch_types_batch_three(self) -> None:
        """Test batch_three mode."""
        body = GenerateQARequest(mode="batch_three")
        result = _resolve_stream_batch_types(body)
        assert isinstance(result, list)


class TestStreamBatchState:
    """Test stream batch state management."""

    def test_stream_batch_state_initialization(self) -> None:
        """Test state initialization with defaults."""
        state = _StreamBatchState()

        assert state.completed_queries == []
        assert state.success_count == 0
        assert state.first_answer == ""

    def test_stream_batch_state_update(self) -> None:
        """Test state updates during streaming."""
        state = _StreamBatchState()

        state.completed_queries.append("질문1")
        state.success_count += 1
        state.first_answer = "첫 번째 답변"

        assert len(state.completed_queries) == 1
        assert state.success_count == 1
        assert state.first_answer == "첫 번째 답변"


class TestReasoningTaskManagement:
    """Test reasoning task management."""

    def test_maybe_start_reasoning_task_when_present(self) -> None:
        """Test starting reasoning task when it's first in remaining types."""
        remaining_types = ["reasoning", "target_short"]
        mock_agent = Mock()

        with patch("src.web.routers.qa.generate_single_qa_with_retry") as mock_gen:
            mock_gen.return_value = asyncio.Future()
            mock_gen.return_value.set_result({"query": "Q", "answer": "A"})

            task, new_remaining = _maybe_start_reasoning_task(
                remaining_types, mock_agent, "OCR"
            )

            assert task is not None
            assert new_remaining == ["target_short"]

    def test_maybe_start_reasoning_task_when_not_present(self) -> None:
        """Test when reasoning is not first."""
        remaining_types = ["target_short", "target_long"]
        mock_agent = Mock()

        task, new_remaining = _maybe_start_reasoning_task(
            remaining_types, mock_agent, "OCR"
        )

        assert task is None
        assert new_remaining == remaining_types

    def test_maybe_start_reasoning_task_empty_list(self) -> None:
        """Test with empty remaining types."""
        remaining_types: list[str] = []
        mock_agent = Mock()

        task, new_remaining = _maybe_start_reasoning_task(
            remaining_types, mock_agent, "OCR"
        )

        assert task is None
        assert new_remaining == []


class TestYieldCompletedReasoningTask:
    """Test reasoning task completion yielding."""

    @pytest.mark.asyncio
    async def test_yield_completed_reasoning_task_success(self) -> None:
        """Test yielding successful reasoning task result."""
        state = _StreamBatchState()

        # Create a completed task
        async def completed_task() -> dict[str, Any]:
            return {"query": "Q", "answer": "A"}

        task = asyncio.create_task(completed_task())
        await task  # Ensure it's done

        events = [event async for event in _yield_completed_reasoning_task(task, state)]

        assert len(events) == 1
        assert "reasoning" in events[0]
        assert state.success_count == 1
        assert len(state.completed_queries) == 1

    @pytest.mark.asyncio
    async def test_yield_completed_reasoning_task_error(self) -> None:
        """Test yielding failed reasoning task."""
        state = _StreamBatchState()

        # Create a failed task
        async def failing_task() -> dict[str, Any]:
            raise ValueError("생성 실패")

        task = asyncio.create_task(failing_task())
        with contextlib.suppress(ValueError):
            await task

        events = [event async for event in _yield_completed_reasoning_task(task, state)]

        assert len(events) == 1
        assert '"error"' in events[0]
        assert state.success_count == 0

    @pytest.mark.asyncio
    async def test_yield_completed_reasoning_task_none(self) -> None:
        """Test with no reasoning task."""
        state = _StreamBatchState()

        events = [event async for event in _yield_completed_reasoning_task(None, state)]

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_yield_completed_reasoning_task_not_done(self) -> None:
        """Test with task that's not done yet."""
        state = _StreamBatchState()

        # Create a task that's not done yet (using asyncio.Future that never completes)
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        task = asyncio.create_task(future)

        events = [event async for event in _yield_completed_reasoning_task(task, state)]

        assert len(events) == 0
        task.cancel()


class TestCreateStreamTasks:
    """Test stream task creation."""

    def test_create_stream_tasks_creates_all_tasks(self) -> None:
        """Test creating tasks for all remaining types."""
        remaining_types = ["target_short", "target_long"]
        mock_agent = Mock()

        with patch("src.web.routers.qa.generate_single_qa_with_retry") as mock_gen:
            mock_gen.return_value = asyncio.Future()
            mock_gen.return_value.set_result({"query": "Q", "answer": "A"})

            task_map = _create_stream_tasks(remaining_types, mock_agent, "OCR", [], "")

            assert len(task_map) == 2
            for qtype in task_map.values():
                assert qtype in remaining_types

    def test_create_stream_tasks_passes_previous_queries(self) -> None:
        """Test that previous queries are passed to task creation."""
        remaining_types = ["target_short"]
        mock_agent = Mock()
        completed_queries = ["이전 질문1", "이전 질문2"]
        first_answer = "첫 답변"

        with patch("src.web.routers.qa.generate_single_qa_with_retry") as mock_gen:
            mock_gen.return_value = asyncio.Future()
            mock_gen.return_value.set_result({"query": "Q", "answer": "A"})

            task_map = _create_stream_tasks(
                remaining_types,
                mock_agent,
                "OCR",
                completed_queries,
                first_answer,
            )

            assert len(task_map) == 1


class TestBuildTaskMap:
    """Test task map building."""

    def test_build_task_map_with_remaining_types(self) -> None:
        """Test building task map with remaining types."""
        remaining_types = ["target_short"]
        mock_agent = Mock()
        state = _StreamBatchState()

        with patch("src.web.routers.qa._create_stream_tasks") as mock_create:
            mock_create.return_value = {"task": "target_short"}

            task_map = _build_task_map(remaining_types, mock_agent, "OCR", state, None)

            assert task_map == {"task": "target_short"}
            mock_create.assert_called_once()

    def test_build_task_map_with_reasoning_task(self) -> None:
        """Test building task map with reasoning task."""
        remaining_types: list[str] = []
        mock_agent = Mock()
        state = _StreamBatchState()
        reasoning_task = Mock()

        task_map = _build_task_map(
            remaining_types, mock_agent, "OCR", state, reasoning_task
        )

        assert reasoning_task in task_map
        assert task_map[reasoning_task] == "reasoning"

    def test_build_task_map_empty(self) -> None:
        """Test building task map with no types and no reasoning."""
        remaining_types: list[str] = []
        mock_agent = Mock()
        state = _StreamBatchState()

        task_map = _build_task_map(remaining_types, mock_agent, "OCR", state, None)

        assert len(task_map) == 0


class TestStreamBatchQAGeneration:
    """Test main streaming endpoint."""

    @pytest.mark.asyncio
    async def test_stream_batch_qa_generation_invalid_mode(self) -> None:
        """Test streaming with invalid mode."""
        body = GenerateQARequest(mode="single")

        with pytest.raises(HTTPException) as exc_info:
            await stream_batch_qa_generation(body)

        assert exc_info.value.status_code == 400
        assert "스트리밍은 batch/batch_three만 지원" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_batch_qa_generation_no_agent(self) -> None:
        """Test streaming when agent not initialized."""
        body = GenerateQARequest(mode="batch")

        with patch("src.web.routers.qa._get_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await stream_batch_qa_generation(body)

            assert exc_info.value.status_code == 500
            assert "Agent 초기화 실패" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_batch_qa_generation_uses_provided_ocr(self) -> None:
        """Test streaming uses OCR from request."""
        body = GenerateQARequest(mode="batch", ocr_text="직접 제공 OCR")

        mock_agent = Mock()
        with (
            patch("src.web.routers.qa._get_agent", return_value=mock_agent),
            patch("src.web.routers.qa._get_config") as mock_cfg,
            patch("src.web.routers.qa._stream_batch_events") as mock_stream,
        ):
            mock_cfg.return_value = Mock()

            async def dummy_stream(*args: Any) -> AsyncIterator[str]:
                # Empty generator for testing
                return
                yield  # Never reached, but needed for type checking

            mock_stream.return_value = dummy_stream()

            response = await stream_batch_qa_generation(body)

            assert response is not None
            # Verify _stream_batch_events was called with provided OCR
            mock_stream.assert_called_once()
            call_args = mock_stream.call_args
            assert call_args[0][2] == "직접 제공 OCR"


class TestStreamBatchEventsIntegration:
    """Integration tests for stream batch events."""

    @pytest.mark.asyncio
    async def test_stream_batch_events_empty_batch_types(self) -> None:
        """Test streaming with empty batch types."""
        from src.web.routers.qa import _stream_batch_events

        body = GenerateQARequest(mode="batch", batch_types=[])
        mock_agent = Mock()

        events = [
            event async for event in _stream_batch_events(body, mock_agent, "OCR")
        ]

        # Should emit error and done events
        assert any("error" in e for e in events)
        assert any("done" in e for e in events)

    @pytest.mark.asyncio
    async def test_stream_batch_events_with_single_type(self) -> None:
        """Test streaming with single QA type."""
        from src.web.routers.qa import _stream_batch_events

        body = GenerateQARequest(mode="batch", batch_types=["explanation"])
        mock_agent = Mock()

        with patch("src.web.routers.qa.generate_single_qa_with_retry") as mock_gen:
            mock_gen.return_value = {"query": "Q", "answer": "A"}

            events = [
                event async for event in _stream_batch_events(body, mock_agent, "OCR")
            ]

            # Should emit: started, progress, done
            assert any("started" in e for e in events)
            assert any("progress" in e for e in events)
            assert any("done" in e for e in events)


class TestEmitFirstTypeEvents:
    """Test first type event emission."""

    @pytest.mark.asyncio
    async def test_emit_first_type_events_success(self) -> None:
        """Test emitting events for first type successfully."""
        from src.web.routers.qa import _emit_first_type_events

        mock_agent = Mock()
        state = _StreamBatchState()

        with patch("src.web.routers.qa._stream_first_batch_type") as mock_stream:
            mock_stream.return_value = (
                "첫 답변",
                ["첫 질문"],
                1,
                ['data: {"event": "progress"}\n\n'],
            )

            events = [
                event
                async for event in _emit_first_type_events(
                    mock_agent, "OCR", "explanation", state
                )
            ]

            assert len(events) == 1
            assert state.first_answer == "첫 답변"
            assert state.success_count == 1
            assert len(state.completed_queries) == 1


class TestEmitRemainingTypeEvents:
    """Test remaining type event emission."""

    @pytest.mark.asyncio
    async def test_emit_remaining_type_events_no_types(self) -> None:
        """Test with no remaining types."""
        from src.web.routers.qa import _emit_remaining_type_events

        state = _StreamBatchState()

        events = [
            event
            async for event in _emit_remaining_type_events(
                [], Mock(), "OCR", state, reasoning_task=None
            )
        ]

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_emit_remaining_type_events_handles_errors(self) -> None:
        """Test error handling in remaining type events."""
        from src.web.routers.qa import _emit_remaining_type_events

        state = _StreamBatchState()
        mock_agent = Mock()

        with patch("src.web.routers.qa._build_task_map") as mock_build:
            # Create a failed task
            async def failing_task() -> dict[str, Any]:
                raise ValueError("태스크 실패")

            task = asyncio.create_task(failing_task())
            with contextlib.suppress(ValueError):
                await task

            mock_build.return_value = {task: "target_short"}

            events = [
                event
                async for event in _emit_remaining_type_events(
                    ["target_short"], mock_agent, "OCR", state
                )
            ]

            # Should emit error event
            assert any("error" in e for e in events)
