"""Streaming batch QA generation endpoint."""
# mypy: disable-error-code=unused-ignore

from __future__ import annotations

import asyncio
import json
import logging
from typing import (
    TYPE_CHECKING,
    AsyncIterator,
    Awaitable,
    Callable,
    Any,
    TypeVar,
    cast,
)

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.config.constants import QA_BATCH_TYPES, QA_BATCH_TYPES_THREE

if TYPE_CHECKING:
    from src.web.models import GenerateQARequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qa-streaming"])
StreamHandler = TypeVar(
    "StreamHandler", bound=Callable[..., Awaitable[StreamingResponse]]
)
stream_route: Callable[[StreamHandler], StreamHandler] = cast(  # type: ignore[redundant-cast]
    "Callable[[StreamHandler], StreamHandler]", router.post("/qa/generate/batch/stream")
)


@stream_route  # type: ignore[misc]
async def stream_batch_qa_generation(body: "GenerateQARequest") -> StreamingResponse:
    """배치 QA 생성 (SSE 스트리밍). batch/batch_three 모드 전용."""
    from src.web.routers.qa_common import _get_agent, _get_config
    from src.web.routers.qa_generation import generate_single_qa_with_retry
    from src.web.utils import load_ocr_text

    if body.mode not in {"batch", "batch_three"}:
        raise HTTPException(
            status_code=400, detail="스트리밍은 batch/batch_three만 지원"
        )

    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")
    ocr_text = body.ocr_text or load_ocr_text(_get_config())

    async def event_generator() -> AsyncIterator[str]:
        batch_types = body.batch_types or QA_BATCH_TYPES
        if body.mode == "batch_three" and body.batch_types is None:
            batch_types = QA_BATCH_TYPES_THREE

        if not batch_types:
            yield f"data: {json.dumps({'event': 'error', 'error': 'batch_types 비어있음'})}\\n\\n"
            yield f"data: {json.dumps({'event': 'done', 'success': False})}\\n\\n"
            return

        yield f"data: {json.dumps({'event': 'started', 'total': len(batch_types)})}\\n\\n"

        completed_queries: list[str] = []
        success_count = 0

        first_type = batch_types[0]
        first_answer = ""
        try:
            first_result = await asyncio.wait_for(
                generate_single_qa_with_retry(current_agent, ocr_text, first_type),
                timeout=_get_config().qa_single_timeout,
            )
            yield f"data: {json.dumps({'event': 'progress', 'type': first_type, 'data': first_result})}\\n\\n"
            if first_result.get("query"):
                completed_queries.append(first_result["query"])
            first_answer = first_result.get("answer", "")
            success_count += 1
        except Exception as exc:
            logger.error(f"{first_type} 실패: {exc}")
            yield f"data: {json.dumps({'event': 'error', 'type': first_type, 'error': str(exc)})}\\n\\n"

        remaining_types = batch_types[1:]
        if remaining_types:
            task_map: dict[asyncio.Future[dict[str, Any]], str] = {}
            task_list: list[asyncio.Future[dict[str, Any]]] = []
            for qtype in remaining_types:
                coro = generate_single_qa_with_retry(
                    current_agent,
                    ocr_text,
                    qtype,
                    previous_queries=completed_queries if completed_queries else None,
                    explanation_answer=first_answer
                    if qtype.startswith("target")
                    else None,
                )
                fut: asyncio.Future[dict[str, Any]] = asyncio.ensure_future(
                    asyncio.wait_for(coro, timeout=_get_config().qa_single_timeout)
                )
                task_map[fut] = qtype
                task_list.append(fut)

            for fut in asyncio.as_completed(task_list):
                qtype = task_map[fut]
                try:
                    result = await fut
                    yield f"data: {json.dumps({'event': 'progress', 'type': qtype, 'data': result})}\\n\\n"
                    if result.get("query"):
                        completed_queries.append(result["query"])
                    success_count += 1
                except Exception as exc:
                    logger.error(f"{qtype} 실패: {exc}")
                    yield f"data: {json.dumps({'event': 'error', 'type': qtype, 'error': str(exc)})}\\n\\n"

        yield f"data: {json.dumps({'event': 'done', 'success': True, 'completed': success_count, 'total': len(batch_types)})}\\n\\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
