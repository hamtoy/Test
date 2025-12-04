# mypy: allow-untyped-decorators
"""워크스페이스 관련 엔드포인트."""

from __future__ import annotations

import asyncio
import logging
import re
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
from src.qa.pipeline import IntegratedQAPipeline
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
pipeline: Optional[IntegratedQAPipeline] = None


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    kg_ref: Optional[QAKnowledgeGraph],
    qa_pipeline: Optional[IntegratedQAPipeline] = None,
) -> None:
    """주요 의존성 주입."""
    global _config, agent, kg, pipeline
    _config = config
    agent = gemini_agent
    kg = kg_ref
    pipeline = qa_pipeline


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


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    try:
        from src.web import api as api_module

        return api_module.pipeline
    except Exception:
        return pipeline


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
    current_pipeline = _get_pipeline()
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
    reference_text = global_explanation_ref or ""

    def _shorten_target_query(text: str) -> str:
        """타겟 단답용 질의가 장문/설명문으로 생성될 때 한 문장으로 압축."""
        clean = re.sub(r"\s+", " ", text or "").strip()
        # 문장 단위로 자르되, 없으면 단어 수로 제한
        parts = re.split(r"[?.!]\s*", clean)
        candidate = parts[0] if parts and parts[0] else clean
        words = candidate.split()
        if len(words) > 20:
            candidate = " ".join(words[:20])
        return candidate.strip()

    def _sanitize_output(text: str) -> str:
        """불릿/마크다운/여분 공백을 제거해 일관된 문장만 남긴다."""
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"[_]{1,2}(.*?)[_]{1,2}", r"\1", text)
        text = text.replace("*", "")
        text = re.sub(r"^[\-\u2022]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _dedup_with_reference(text: str, reference: str, qtype: str) -> str:
        """참조 문단과 중복되는 문장을 제거 (간단 정규화 기반)."""

        def normalize(chunk: str) -> str:
            chunk = chunk.lower()
            chunk = re.sub(r"[\s\*\-_`~#]+", "", chunk)
            chunk = re.sub(r"[.,:;\"'’”“‘!?()/\\]", "", chunk)
            chunk = chunk.replace(",", "")
            return chunk

        ref_norm = normalize(reference)
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()
        ]
        kept: list[str] = []
        for s in sentences:
            norm = normalize(s.strip(" -•\t"))
            if not norm or len(norm) < 10:
                continue
            if norm in ref_norm:
                continue
            kept.append(s.strip())
        if not kept:
            # 타겟 단답일 때는 숫자/퍼센트를 우선 추출해 중복 최소화
            if qtype == "target_short":
                num_match = re.search(
                    r"[0-9][0-9,\.]*\s*억\s*달러|[0-9]+(?:\.[0-9]+)?\s*%|[0-9][0-9,\.]*",
                    text,
                )
                if num_match:
                    return num_match.group(0).strip()
            if qtype in {"target_short", "target_long"}:
                return "참조 내용과 중복되지 않는 추가 정보가 없습니다."
            return sentences[0].strip() if sentences else text.strip()
        return ". ".join(kept[:4])

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
                if query_type == "target_short":
                    query = _shorten_target_query(query)
                changes.append("질의 생성 완료")

            rules_list: list[str] = []
            rule_texts: list[str] = []
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
                try:
                    kg_rules = current_kg.get_rules_for_query_type(normalized_qtype)
                    for r in kg_rules:
                        txt = r.get("text")
                        if txt:
                            rule_texts.append(txt)
                except Exception as exc:
                    logger.debug("Rule 로드 실패: %s", exc)

            if not rules_list:
                rules_list = list(DEFAULT_ANSWER_RULES)

            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 한 문장으로, 최대 50단어 이내로 작성하세요."
                rules_list = rules_list[:3]
            elif query_type == "target_long":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = "불릿·마크다운(볼드/기울임) 없이 한 단락으로 간결하게 추론을 제시하세요."

            dedup_section = ""
            if reference_text:
                dedup_section = f"""
[중복 금지]
다음 전체 설명문에 이미 나온 표현/숫자를 그대로 복사하지 말고, 필요한 경우 다른 문장으로 요약하세요:
---
{reference_text[:500]}
---"""

            rules_text = "\n".join(f"- {r}" for r in rules_list)
            extra_rules_text = "\n".join(f"- {t}" for t in rule_texts[:5])
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}
{dedup_section}

[준수 규칙]
{rules_text}
{extra_rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

            # Direct LLM call for answer generation (not rewrite)
            system_prompt = (
                "당신은 한국어로 정확하고 간결한 답변을 작성하는 어시스턴트입니다."
            )
            model = current_agent._create_generative_model(system_prompt)
            answer = await current_agent._call_api_with_retry(model, prompt)
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
            if query_type == "target_short":
                query = _shorten_target_query(query)
            changes.append("질문 생성 완료")

        elif workflow == "answer_generation":
            changes.append("답변 생성 요청")
            rules_list = list(DEFAULT_ANSWER_RULES)
            answer_rule_texts: list[str] = []
            if current_kg is not None:
                try:
                    constraints = current_kg.get_constraints_for_query_type(
                        normalized_qtype
                    )
                    for c in constraints:
                        desc = c.get("description")
                        if desc:
                            rules_list.append(desc)
                except Exception as exc:
                    logger.debug("규칙 로드 실패: %s", exc)
                try:
                    kg_rules = current_kg.get_rules_for_query_type(normalized_qtype)
                    for r in kg_rules:
                        txt = r.get("text")
                        if txt:
                            answer_rule_texts.append(txt)
                except Exception as exc:
                    logger.debug("Rule 로드 실패: %s", exc)

            rules_text = "\n".join(f"- {r}" for r in rules_list)
            extra_rules_text = "\n".join(f"- {t}" for t in answer_rule_texts[:5])
            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 한 문장으로, 최대 50단어 이내로 작성하세요."
            elif query_type == "target_long":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = (
                    "불릿·마크다운(볼드/기울임) 없이 한 단락으로 간결하게 추론을 제시하세요. "
                    "근거/추론/결론 같은 섹션 제목은 사용하지 마세요."
                )

            dedup_section = ""
            if reference_text:
                dedup_section = f"""
[중복 금지]
다음 전체 설명문에 이미 나온 표현/숫자를 그대로 복사하지 말고, 필요한 경우 다른 문장으로 요약하세요:
---
{reference_text[:500]}
---"""
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}
{dedup_section}

[준수 규칙]
{rules_text}
{extra_rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

[추가 지침]
{body.edit_request or "(없음)"}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

            # Direct LLM call for answer generation
            system_prompt = (
                "당신은 한국어로 정확하고 간결한 답변을 작성하는 어시스턴트입니다."
            )
            model = current_agent._create_generative_model(system_prompt)
            answer = await current_agent._call_api_with_retry(model, prompt)
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
            if current_pipeline is not None:
                try:
                    validation = current_pipeline.validate_output(
                        normalized_qtype, answer
                    )
                    if not validation.get("valid", True):
                        violations = validation.get("violations", [])
                        if violations:
                            changes.append(
                                f"규칙 위반 감지: {', '.join(violations[:3])}"
                            )
                    missing_rules = validation.get("missing_rules_hint", [])
                    if missing_rules:
                        changes.append(
                            f"추가 검증 필요 규칙: {', '.join(missing_rules[:3])}"
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Pipeline validation skipped: %s", exc)
            answer = postprocess_answer(answer, query_type)
            if reference_text and query_type in {
                "target_short",
                "target_long",
                "reasoning",
            }:
                answer = _dedup_with_reference(answer, reference_text, query_type)

            answer = _sanitize_output(answer)

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
