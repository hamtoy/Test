"""WorkspaceExecutor 사용 예제.

이 파일은 workspace router에서 WorkspaceExecutor를 사용하는 방법을 보여줍니다.
실제 통합 시 workspace.py의 api_unified_workspace 함수를 이 패턴으로 리팩토링할 수 있습니다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry
from src.web.utils import detect_workflow, load_ocr_text
from src.workflow.workspace_executor import (
    WorkflowContext,
    WorkflowType,
    WorkspaceExecutor,
)


async def execute_workspace_workflow_example(
    query: str | None,
    answer: str | None,
    ocr_text: str | None,
    query_type: str | None,
    edit_request: str | None,
    global_explanation_ref: str | None,
    use_lats: bool = False,
) -> Any:
    """WorkspaceExecutor를 사용한 통합 워크스페이스 실행 예제.

    Args:
        query: 사용자 질의
        answer: 사용자 답변
        ocr_text: OCR 텍스트
        query_type: 질의 타입
        edit_request: 편집 요청
        global_explanation_ref: 전역 설명 참조
        use_lats: LATS 사용 여부

    Returns:
        API 응답 딕셔너리

    Example:
        이 함수를 workspace router의 api_unified_workspace에서 다음과 같이 사용:

        @router.post("/workspace/unified")
        async def api_unified_workspace(body: UnifiedWorkspaceRequest):
            return await execute_workspace_workflow_example(
                query=body.query,
                answer=body.answer,
                ocr_text=body.ocr_text,
                query_type=body.query_type,
                edit_request=body.edit_request,
                global_explanation_ref=body.global_explanation_ref,
                use_lats=body.use_lats or False,
            )
    """
    registry = get_registry()
    meta_start = datetime.now()

    # ServiceRegistry에서 서비스 가져오기
    config = registry.config
    agent = registry.agent
    kg = registry.kg
    pipeline = registry.pipeline

    # OCR 텍스트 로드
    final_ocr_text = ocr_text or await load_ocr_text(config)

    # 워크플로우 감지
    workflow_str = detect_workflow(query or "", answer or "", edit_request or "")
    workflow_type = WorkflowType(workflow_str)

    # 컨텍스트 구성
    context = WorkflowContext(
        query=query or "",
        answer=answer or "",
        ocr_text=final_ocr_text,
        query_type=query_type or "global_explanation",
        edit_request=edit_request or "",
        global_explanation_ref=global_explanation_ref or "",
        use_lats=use_lats,
    )

    # Executor 생성 및 실행
    executor = WorkspaceExecutor(
        agent=agent,
        kg=kg,
        pipeline=pipeline,
        config=config,
    )

    try:
        result = await asyncio.wait_for(
            executor.execute(workflow_type, context),
            timeout=config.workspace_unified_timeout,
        )

        # 결과를 Dict로 변환
        result_dict = {
            "workflow": result.workflow,
            "query": result.query,
            "answer": result.answer,
            "changes": result.changes,
            "query_type": result.query_type,
        }

        # 응답 구성
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)

        return build_response(result_dict, metadata=meta, config=config)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({config.workspace_unified_timeout}초)",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="워크플로우 실행 중 오류가 발생했습니다."
        )
