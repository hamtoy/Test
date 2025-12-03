# mypy: allow-untyped-decorators
"""워크스페이스 관련 엔드포인트."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from checks.detect_forbidden_patterns import find_violations
from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
)
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import UnifiedWorkspaceRequest, WorkspaceRequest
from src.web.utils import (
    QTYPE_MAP,
    detect_workflow,
    load_ocr_text,
    log_review_session,
    postprocess_answer,
    strip_output_tags,
)
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace"])

_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    kg_ref: Optional[QAKnowledgeGraph],
) -> None:
    """주요 의존성 주입."""
    global _config, agent, kg
    _config = config
    agent = gemini_agent
    kg = kg_ref


def _get_agent() -> Optional[GeminiAgent]:
    try:
        from src.web import api as api_module

        return api_module.agent
    except Exception:
        return agent


def _get_kg() -> Optional[QAKnowledgeGraph]:
    try:
        from src.web import api as api_module

        return api_module.kg
    except Exception:
        return kg


def _get_config() -> AppConfig:
    if _config is not None:
        return _config
    try:
        from src.web import api as api_module

        return api_module.get_config()
    except Exception:
        return AppConfig()


@router.post("/workspace")
async def api_workspace(body: WorkspaceRequest) -> Dict[str, Any]:
    """검수 또는 자유 수정."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = load_ocr_text(_get_config())

    async def _run_workspace() -> Dict[str, Any]:
        if body.mode == "inspect":
            fixed = await inspect_answer(
                agent=current_agent,
                answer=body.answer,
                query=body.query or "",
                ocr_text=ocr_text,
                context={},
                kg=current_kg,
                validator=None,
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
        return await asyncio.wait_for(
            _run_workspace(), timeout=WORKSPACE_GENERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"작업 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error("워크스페이스 작업 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"작업 실패: {str(e)}")


@router.post("/workspace/generate-answer")
async def api_generate_answer_from_query(body: Dict[str, Any]) -> Dict[str, Any]:
    """질문 기반 답변 생성 - Neo4j 규칙 동적 주입."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    query = body.get("query", "")
    ocr_text = body.get("ocr_text") or load_ocr_text(_get_config())
    query_type = body.get("query_type", "explanation")
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")

    rules_list: list[str] = []
    if current_kg is not None:
        try:
            constraints = current_kg.get_constraints_for_query_type(normalized_qtype)
            for c in constraints:
                desc = c.get("description")
                if desc:
                    rules_list.append(desc)
        except Exception as e:
            logger.debug("규칙 로드 실패: %s", e)

    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)

    try:
        rules_text = "\n".join(f"- {r}" for r in rules_list)
        prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
표/그래프/차트를 직접 언급하지 말고 텍스트 근거만 사용하세요.
<output> 태그를 사용하지 마세요.

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

        위 OCR 텍스트를 기반으로 질의에 대한 답변을 작성하세요."""

        answer = await asyncio.wait_for(
            current_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            ),
            timeout=WORKSPACE_GENERATION_TIMEOUT,
        )

        answer = strip_output_tags(answer)

        violations = find_violations(answer)
        if violations:
            violation_types = ", ".join(set(v["type"] for v in violations))
            answer = await asyncio.wait_for(
                current_agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=answer,
                    edit_request=f"한국어로 다시 작성하고 다음 패턴 제거: {violation_types}. <output> 태그 사용 금지.",
                    cached_content=None,
                    query_type=normalized_qtype,
                ),
                timeout=WORKSPACE_GENERATION_TIMEOUT,
            )
            answer = strip_output_tags(answer)

        return {"query": query, "answer": answer}
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"답변 생성 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspace/generate-query")
async def api_generate_query_from_answer(body: Dict[str, Any]) -> Dict[str, Any]:
    """답변 기반 질문 생성."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    answer = body.get("answer", "")
    ocr_text = body.get("ocr_text") or load_ocr_text(_get_config())

    try:
        prompt = f"""
다음 답변에 가장 적합한 질문을 생성하세요.

[OCR 텍스트]
{ocr_text[:1000]}

[답변]
{answer}

        위 답변에 대한 자연스러운 질문 1개를 생성하세요. 질문만 출력하세요.
"""
        queries = await asyncio.wait_for(
            current_agent.generate_query(prompt, user_intent=None),
            timeout=WORKSPACE_GENERATION_TIMEOUT,
        )
        query = queries[0] if queries else "질문 생성 실패"

        return {"query": query, "answer": answer}
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"질의 생성 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - 모든 조합 지원."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text(_get_config())
    query_type = body.query_type or "global_explanation"
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")
    global_explanation_ref = body.global_explanation_ref or ""

    query_intent = None
    if query_type == "target_short":
        query_intent = "간단한 사실 확인 질문"
        if global_explanation_ref:
            query_intent += f"""

[중복 방지 필수]
다음 전체 설명문에서 이미 다룬 내용과 중복되지 않는 새로운 세부 사실/수치를 질문하세요:
---
{global_explanation_ref[:500]}
---
전체 설명에서 다루지 않은 구체적 정보(날짜, 수치, 특정 명칭 등)에 집중하세요."""
    elif query_type == "target_long":
        query_intent = "핵심 요점을 묻는 질문"
        if global_explanation_ref:
            query_intent += f"""

[중복 방지 필수]
다음 전체 설명문과 다른 관점의 핵심 요점을 질문하세요:
---
{global_explanation_ref[:500]}
---"""
    elif query_type == "reasoning":
        query_intent = "추론/예측 질문"
    elif query_type == "global_explanation":
        query_intent = "전체 내용 설명 질문"

    workflow = detect_workflow(body.query or "", body.answer or "", body.edit_request)
    logger.info("워크플로우 감지: %s, 질문 유형: %s", workflow, query_type)

    query = body.query or ""
    answer = body.answer or ""
    changes: list[str] = []

    async def _execute_workflow() -> Dict[str, Any]:
        nonlocal query, answer
        if workflow == "full_generation":
            changes.append("OCR에서 전체 생성")

            queries = await current_agent.generate_query(
                ocr_text,
                user_intent=query_intent,
                query_type=query_type,
                kg=current_kg,
            )
            if queries:
                query = queries[0]
                changes.append("질의 생성 완료")

            rules_list: list[str] = []
            if current_kg is not None:
                try:
                    constraints = current_kg.get_constraints_for_query_type(
                        normalized_qtype
                    )
                    for c in constraints:
                        desc = c.get("description")
                        if desc:
                            rules_list.append(desc)
                except Exception as e:
                    logger.debug("규칙 로드 실패: %s", e)

            if not rules_list:
                rules_list = list(DEFAULT_ANSWER_RULES)

            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 1-2문장, 최대 50단어 이내로 작성하세요."
                rules_list = rules_list[:3]
            elif query_type == "target_long":
                length_constraint = "답변은 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = "근거 2~3개와 결론을 명확히 제시하세요."

            rules_text = "\n".join(f"- {r}" for r in rules_list)
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

            answer = await current_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            )
            answer = strip_output_tags(answer)
            changes.append("답변 생성 완료")

        elif workflow == "query_generation":
            changes.append("질문 생성 요청")
            queries = await current_agent.generate_query(
                ocr_text,
                user_intent=query_intent,
                query_type=query_type,
                kg=current_kg,
            )
            query = queries[0] if queries else "질문 생성 실패"
            changes.append("질문 생성 완료")

        elif workflow == "answer_generation":
            changes.append("답변 생성 요청")
            rules_list = list(DEFAULT_ANSWER_RULES)
            rules_text = "\n".join(f"- {r}" for r in rules_list)
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

            answer = await current_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            )
            answer = strip_output_tags(answer)
            changes.append("답변 생성 완료")

        elif workflow == "rewrite":
            changes.append("답변 재작성 요청")
            answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request="형식/길이 위반을 자동 교정",
                kg=current_kg,
                cache=None,
            )
            answer = strip_output_tags(answer)
            changes.append("재작성 완료")

        elif workflow == "edit_query":
            changes.append("질의 수정 요청")
            edited_query = await edit_content(
                agent=current_agent,
                answer=query,
                ocr_text=ocr_text,
                query="",
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 수정 완료")

        elif workflow == "edit_answer":
            changes.append(f"답변 수정 요청: {body.edit_request}")
            edited_answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

        elif workflow == "edit_both":
            changes.append(f"질의+답변 수정 요청: {body.edit_request}")
            edited_answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

            edited_query = await edit_content(
                agent=current_agent,
                answer=query,
                ocr_text=ocr_text,
                query="",
                edit_request=f"다음 답변에 맞게 질의 조정: {answer[:200]}...",
                kg=current_kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 조정 완료")

        else:
            raise HTTPException(status_code=400, detail="알 수 없는 워크플로우")

        if answer:
            answer = postprocess_answer(answer, query_type)

        return {
            "workflow": workflow,
            "query": query,
            "answer": answer,
            "changes": changes,
            "query_type": query_type,
        }

    try:
        return await asyncio.wait_for(
            _execute_workflow(), timeout=WORKSPACE_UNIFIED_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({WORKSPACE_UNIFIED_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error("워크플로우 실행 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"실행 실패: {str(e)}")


__all__ = [
    "api_generate_answer_from_query",
    "api_generate_query_from_answer",
    "api_unified_workspace",
    "api_workspace",
    "router",
    "set_dependencies",
]
