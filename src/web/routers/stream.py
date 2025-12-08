# mypy: allow-untyped-decorators
"""Streaming response endpoints."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.agent import GeminiAgent
from src.config import AppConfig
from src.web import api as api_module
from src.web.models import StreamGenerateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stream"])

_config: AppConfig | None = None
agent: GeminiAgent | None = None


def set_dependencies(config: AppConfig, gemini_agent: GeminiAgent) -> None:
    """주요 의존성 주입."""
    global _config, agent
    _config = config
    agent = gemini_agent


def _get_agent() -> GeminiAgent:
    """스트리밍에 사용할 에이전트를 가져온다.

    테스트에서는 src.web.api.agent 를 패치하므로, 주입된 에이전트가 없으면
    api_module.agent 를 동적으로 조회한다.
    """
    if agent is not None:
        return agent
    current_agent = getattr(api_module, "agent", None)
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")
    return cast("GeminiAgent", current_agent)


@router.post("/qa/generate/stream")
async def api_generate_qa_stream(body: StreamGenerateRequest) -> StreamingResponse:
    """QA 생성 스트리밍 (SSE)."""
    current_agent = _get_agent()

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in current_agent.generate_stream(
                body.prompt,
                system_instruction=body.system_instruction,
            ):
                yield f"data: {json.dumps({'text': chunk})}\\n\\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("Streaming generation failed: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\\n\\n"
        yield "data: [DONE]\\n\\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


__all__ = ["api_generate_qa_stream", "router", "set_dependencies"]
