"""워크스페이스 통합 워크플로우 엔드포인트.

웹앱 사용 여부: ✅ 활성 사용 중 (메인)

- 웹 페이지: /workspace (templates/web/workspace.html)
- 프론트엔드: static/dist/chunks/workspace.js
- 엔드포인트: POST /api/workspace/unified
- 용도: 통합 워크스페이스 - WorkspaceExecutor 기반으로 질의/답변 생성, 수정, 검수 등 모든 워크플로우 처리
- 아키텍처: WorkflowType(full_generation, query_generation, answer_generation, rewrite, edit_query, edit_answer, edit_both) 자동 감지 및 실행
"""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from src.web.models import UnifiedWorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.utils import detect_workflow, load_ocr_text
from src.workflow.edit import edit_content

from .workspace_common import _get_agent, _get_config, _get_kg, _get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace-unified"])


@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> dict[str, Any]:
    """통합 워크스페이스 - WorkspaceExecutor 기반 구현."""
    from src.workflow.workspace_executor import (
        WorkflowContext,
        WorkflowType,
        WorkspaceExecutor,
    )

    # Get services from registry
    current_agent = _get_agent()
    current_kg = _get_kg()
    current_pipeline = _get_pipeline()
    config = _get_config()
    meta_start = datetime.now()

    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    # Load OCR text
    ocr_text = body.ocr_text or load_ocr_text(config)

    # Detect workflow
    workflow_str = detect_workflow(
        body.query or "",
        body.answer or "",
        body.edit_request or "",
    )

    try:
        workflow_type = WorkflowType(workflow_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없는 워크플로우: {workflow_str}",
        )

    # Build context
    context = WorkflowContext(
        query=body.query or "",
        answer=body.answer or "",
        ocr_text=ocr_text,
        query_type=body.query_type or "global_explanation",
        edit_request=body.edit_request or "",
        global_explanation_ref=body.global_explanation_ref or "",
        use_lats=body.use_lats or False,
    )

    # Create executor and execute workflow
    executor = WorkspaceExecutor(
        agent=current_agent,
        kg=current_kg,
        pipeline=current_pipeline,
        config=config,
        edit_fn=edit_content,
    )

    try:
        result = await asyncio.wait_for(
            executor.execute(workflow_type, context),
            timeout=config.workspace_unified_timeout,
        )

        # Build response
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)

        result_dict = {
            "workflow": result.workflow,
            "query": result.query,
            "answer": result.answer,
            "changes": result.changes,
            "query_type": result.query_type,
        }

        return cast(
            "dict[str, Any]",
            build_response(result_dict, metadata=meta, config=config),
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({config.workspace_unified_timeout}초). 다시 시도해주세요.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("워크플로우 실행 실패: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"실행 실패: {e!s}")
