"""워크스페이스 검수 및 수정 엔드포인트."""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, cast

from fastapi import APIRouter, HTTPException

from src.web.models import WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.utils import load_ocr_text, log_review_session
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

from .workspace_common import _get_agent, _get_config, _get_kg, _get_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace-review"])


@router.post("/workspace")
async def api_workspace(body: WorkspaceRequest) -> Dict[str, Any]:
    """검수 또는 자유 수정."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    config = _get_config()
    ocr_text = load_ocr_text(config)
    meta_start = datetime.now()

    async def _run_workspace() -> Dict[str, Any]:
        if body.mode == "inspect":
            fixed = await inspect_answer(
                agent=current_agent,
                answer=body.answer,
                query=body.query or "",
                ocr_text=ocr_text,
                context={},
                kg=current_kg,
                validator=_get_validator(),
                cache=None,
            )

            log_review_session(
                mode="inspect",
                question=body.query or "",
                answer_before=body.answer,
                answer_after=fixed,
                edit_request_used="",
                inspector_comment=body.inspector_comment or "",
            )

            return {
                "mode": "inspect",
                "result": {
                    "original": body.answer,
                    "fixed": fixed,
                    "changes": ["자동 교정 완료"],
                },
            }

        if not body.edit_request:
            raise HTTPException(status_code=400, detail="edit_request가 필요합니다.")

        edited = await edit_content(
            agent=current_agent,
            answer=body.answer,
            ocr_text=ocr_text,
            query=body.query or "",
            edit_request=body.edit_request,
            kg=current_kg,
            cache=None,
        )

        log_review_session(
            mode="edit",
            question=body.query or "",
            answer_before=body.answer,
            answer_after=edited,
            edit_request_used=body.edit_request,
            inspector_comment=body.inspector_comment or "",
        )

        return {
            "mode": "edit",
            "result": {
                "original": body.answer,
                "edited": edited,
                "request": body.edit_request,
            },
        }

    try:
        result = await asyncio.wait_for(
            _run_workspace(), timeout=config.workspace_timeout
        )
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any], build_response(result, metadata=meta, config=config)
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"작업 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error("워크스페이스 작업 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"작업 실패: {str(e)}")
