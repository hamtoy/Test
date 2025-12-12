"""QA 생성 및 평가 엔드포인트 (메인 라우터 집합)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.config.constants import QA_BATCH_TYPES, QA_BATCH_TYPES_THREE
from src.web.models import GenerateQARequest

# Import sub-routers
from . import qa_common, qa_evaluation, qa_generation, qa_tools

logger = logging.getLogger(__name__)

# Main QA router that aggregates all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(qa_generation.router)
router.include_router(qa_evaluation.router)
router.include_router(qa_tools.router)

# Export set_dependencies for backward compatibility
set_dependencies = qa_common.set_dependencies

# Export commonly used items for backward compatibility
from src.web.utils import load_ocr_text  # noqa: E402

from .qa_common import (  # noqa: F401, E402
    _CachedKG,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator_class,
    get_cached_kg,
)

# Export helper functions for backward compatibility
from .qa_generation import (  # noqa: E402
    generate_single_qa,
    generate_single_qa_with_retry,
)

# =====================================================
# Streaming endpoint (migrated from qa_streaming.py)
# =====================================================

streaming_router = APIRouter(prefix="/api", tags=["qa-streaming"])
stream_route = streaming_router.post("/qa/generate/batch/stream")


def _sse(event: str, **payload: Any) -> str:
    return f"data: {json.dumps({'event': event, **payload})}\n\n"


def _resolve_stream_batch_types(body: GenerateQARequest) -> list[str]:
    batch_types = body.batch_types or QA_BATCH_TYPES
    if body.mode == "batch_three" and body.batch_types is None:
        batch_types = QA_BATCH_TYPES_THREE
    return list(batch_types)


async def _stream_first_batch_type(
    agent: Any,
    ocr_text: str,
    qtype: str,
    timeout: float,
) -> tuple[str, list[str], int, list[str]]:
    first_answer = ""
    completed: list[str] = []
    events: list[str] = []
    success = 0
    try:
        first_result = await asyncio.wait_for(
            generate_single_qa_with_retry(agent, ocr_text, qtype),
            timeout=timeout,
        )
        events.append(_sse("progress", type=qtype, data=first_result))
        query = first_result.get("query")
        if query:
            completed.append(str(query))
        first_answer = first_result.get("answer", "")
        success = 1
    except Exception as exc:  # noqa: BLE001
        logger.error("%s 실패: %s", qtype, exc)
        events.append(_sse("error", type=qtype, error=str(exc)))
    return first_answer, completed, success, events


def _create_stream_tasks(
    remaining_types: list[str],
    agent: Any,
    ocr_text: str,
    completed_queries: list[str],
    first_answer: str,
    timeout: float,
) -> dict[asyncio.Task[dict[str, Any]], str]:
    task_map: dict[asyncio.Task[dict[str, Any]], str] = {}
    for qtype in remaining_types:
        coro = generate_single_qa_with_retry(
            agent,
            ocr_text,
            qtype,
            previous_queries=completed_queries if completed_queries else None,
            explanation_answer=first_answer if qtype.startswith("target") else None,
        )
        task = asyncio.create_task(asyncio.wait_for(coro, timeout=timeout))
        task_map[task] = qtype
    return task_map


async def _iter_stream_task_results(
    task_map: dict[asyncio.Task[dict[str, Any]], str],
) -> AsyncIterator[tuple[str, dict[str, Any] | None, Exception | None]]:
    pending: set[asyncio.Task[dict[str, Any]]] = set(task_map.keys())
    try:
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                qtype = task_map[task]
                try:
                    yield qtype, task.result(), None
                except Exception as exc:  # noqa: BLE001
                    yield qtype, None, exc
    finally:
        for task in pending:
            task.cancel()


async def _stream_batch_events(
    body: GenerateQARequest,
    agent: Any,
    ocr_text: str,
) -> AsyncIterator[str]:
    batch_types = _resolve_stream_batch_types(body)
    if not batch_types:
        yield _sse("error", error="batch_types 비어있음")
        yield _sse("done", success=False)
        return

    yield _sse("started", total=len(batch_types))

    completed_queries: list[str] = []
    success_count = 0

    timeout = _get_config().qa_single_timeout
    first_type = batch_types[0]
    (
        first_answer,
        first_queries,
        first_success,
        first_events,
    ) = await _stream_first_batch_type(
        agent,
        ocr_text,
        first_type,
        timeout,
    )
    for event in first_events:
        yield event
    completed_queries.extend(first_queries)
    success_count += first_success

    remaining_types = batch_types[1:]
    if remaining_types:
        task_map = _create_stream_tasks(
            remaining_types,
            agent,
            ocr_text,
            completed_queries,
            first_answer,
            timeout,
        )
        async for qtype, result, exc in _iter_stream_task_results(task_map):
            if exc is not None:
                logger.error("%s 실패: %s", qtype, exc)
                yield _sse("error", type=qtype, error=str(exc))
                continue
            if result is None:
                continue
            yield _sse("progress", type=qtype, data=result)
            query = result.get("query")
            if query:
                completed_queries.append(str(query))
            success_count += 1

    yield _sse(
        "done",
        success=True,
        completed=success_count,
        total=len(batch_types),
    )


@stream_route
async def stream_batch_qa_generation(body: GenerateQARequest) -> StreamingResponse:
    """배치 QA 생성 (SSE 스트리밍). batch/batch_three 모드 전용."""
    if body.mode not in {"batch", "batch_three"}:
        raise HTTPException(
            status_code=400, detail="스트리밍은 batch/batch_three만 지원"
        )

    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")
    ocr_text = body.ocr_text or load_ocr_text(_get_config())

    return StreamingResponse(
        _stream_batch_events(body, current_agent, ocr_text),
        media_type="text/event-stream",
    )


# Include the streaming router
router.include_router(streaming_router)

# Export all routers and key functions
__all__ = [
    "_CachedKG",
    "_get_agent",
    "_get_config",
    "_get_kg",
    "_get_pipeline",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "get_cached_kg",
    "qa_common",
    "qa_evaluation",
    "qa_generation",
    "router",
    "set_dependencies",
    "stream_batch_qa_generation",
]
