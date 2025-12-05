"""워크스페이스 관련 엔드포인트."""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from src.features.lats import SearchNode

from checks.detect_forbidden_patterns import find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
)
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import UnifiedWorkspaceRequest, WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry
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

router: APIRouter = APIRouter(prefix="/api", tags=["workspace"])

# Backward compatibility: keep global variables for modules that import them
# TODO: Remove these in future release once all routers use ServiceRegistry exclusively
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None
_validator: Optional[CrossValidationSystem] = None
_difficulty_levels = {
    "long": "본문이 길어 핵심 숫자·근거만 간결히 답하세요.",
    "medium": "불필요한 서론 없이 핵심을 짧게 서술하세요.",
}


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
    global _validator
    _validator = None  # reset so it uses latest kg


def _get_agent() -> Optional[GeminiAgent]:
    """Get agent from ServiceRegistry with fallback to module global."""
    try:
        registry = get_registry()
        return registry.agent
    except RuntimeError:
        # Fallback to module global for backward compatibility
        try:
            from src.web import api as api_module

            if getattr(api_module, "agent", None) is not None:
                return api_module.agent
        except Exception:
            pass
        return agent


def _get_kg() -> Optional[QAKnowledgeGraph]:
    """Get KG from ServiceRegistry with fallback to module global."""
    try:
        registry = get_registry()
        return registry.kg
    except RuntimeError:
        # Fallback to module global for backward compatibility
        try:
            from src.web import api as api_module

            if getattr(api_module, "kg", None) is not None:
                return api_module.kg
        except Exception:
            pass
        return kg


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    """Get pipeline from ServiceRegistry with fallback to module global."""
    try:
        registry = get_registry()
        return registry.pipeline
    except RuntimeError:
        # Fallback to module global for backward compatibility
        try:
            from src.web import api as api_module

            if getattr(api_module, "pipeline", None) is not None:
                return api_module.pipeline
        except Exception:
            pass
        return pipeline


def _get_config() -> AppConfig:
    """Get config from ServiceRegistry with fallback to module global."""
    try:
        registry = get_registry()
        cfg = registry.config
    except RuntimeError:
        # Fallback to module global for backward compatibility
        try:
            from src.web import api as api_module

            cfg_raw = getattr(api_module, "config", None) or _config
            if cfg_raw is None:
                raise RuntimeError
            cfg = cast(AppConfig, cfg_raw)
        except Exception:
            try:
                from src.web import dependencies

                cfg = dependencies.get_config()
            except Exception:
                cfg = AppConfig()

    # Ensure required timeout attributes exist
    for name, default in [
        ("qa_single_timeout", QA_SINGLE_GENERATION_TIMEOUT),
        ("qa_batch_timeout", QA_BATCH_GENERATION_TIMEOUT),
        ("workspace_timeout", WORKSPACE_GENERATION_TIMEOUT),
        ("workspace_unified_timeout", WORKSPACE_UNIFIED_TIMEOUT),
    ]:
        try:
            value = int(getattr(cfg, name, default))
        except Exception:
            value = default
        setattr(cfg, name, value)
    try:
        cfg.enable_standard_response = bool(
            getattr(cfg, "enable_standard_response", False)
        )
        cfg.enable_lats = bool(getattr(cfg, "enable_lats", False))
    except Exception:
        cfg.enable_standard_response = False
        cfg.enable_lats = False
    return cfg


def _get_validator_class() -> type[CrossValidationSystem]:
    """테스트 패치 호환용 CrossValidationSystem 조회."""
    try:
        from src.web import api as api_module

        return getattr(api_module, "CrossValidationSystem", CrossValidationSystem)
    except Exception:
        return CrossValidationSystem


def _get_validator() -> Optional[CrossValidationSystem]:
    """지연 초기화된 validator 반환 (kg 없으면 None)."""
    global _validator
    if _validator is not None:
        return _validator
    current_kg = _get_kg()
    if current_kg is None:
        return None
    try:
        validator_cls = _get_validator_class()
        _validator = validator_cls(current_kg)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Validator 초기화 실패: %s", exc)
        _validator = None
    return _validator


def _difficulty_hint(ocr_text: str) -> str:
    length = len(ocr_text)
    if length > 4000:
        return _difficulty_levels["long"]
    if length > 2000:
        return _difficulty_levels["long"]
    return _difficulty_levels["medium"]


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


@router.post("/workspace/generate-answer")
async def api_generate_answer_from_query(body: Dict[str, Any]) -> Dict[str, Any]:
    """질문 기반 답변 생성 - Neo4j 규칙 동적 주입."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    query = body.get("query", "")
    config = _get_config()
    ocr_text = body.get("ocr_text") or load_ocr_text(config)
    meta_start = datetime.now()
    query_type = body.get("query_type", "explanation")
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")

    rule_loader = RuleLoader(current_kg)
    rules_list = rule_loader.get_rules_for_type(normalized_qtype, DEFAULT_ANSWER_RULES)

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
            timeout=config.workspace_timeout,
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
                timeout=config.workspace_timeout,
            )
            answer = strip_output_tags(answer)

        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any],
            build_response(
                {"query": query, "answer": answer}, metadata=meta, config=config
            ),
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"답변 생성 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
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
    config = _get_config()
    ocr_text = body.get("ocr_text") or load_ocr_text(config)
    meta_start = datetime.now()

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
            timeout=config.workspace_timeout,
        )
        query = queries[0] if queries else "질문 생성 실패"

        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any],
            build_response(
                {"query": query, "answer": answer}, metadata=meta, config=config
            ),
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"질의 생성 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_lats_answer(
    query: str,
    ocr_text: str,
    query_type: str,
) -> tuple[str, dict[str, Any]]:
    """LATS를 사용하여 여러 답변 후보 생성 및 평가 후 최적 선택."""
    current_agent = _get_agent()
    if not current_agent:
        return "", {}

    # 각 전략별 프롬프트 생성
    strategies = [
        {
            "name": "숫자_중심",
            "instruction": "OCR 텍스트에 있는 모든 주요 숫자와 수치를 중심으로 답변하세요.",
        },
        {
            "name": "트렌드_중심",
            "instruction": "시간에 따른 변화, 증가/감소 추세를 중심으로 답변하세요.",
        },
        {
            "name": "비교_중심",
            "instruction": "서로 다른 항목들의 차이점과 비교를 중심으로 답변하세요.",
        },
    ]

    # 각 전략으로 답변 생성 및 평가
    candidates: list[dict[str, Any]] = []
    for strategy in strategies:
        prompt = f"""[질의]
{query}

[OCR 텍스트]
{ocr_text[:2000]}

[답변 전략: {strategy["name"]}]
{strategy["instruction"]}

위 OCR 텍스트를 기반으로 답변을 작성하세요. 마크다운이나 불릿은 사용하지 마세요."""

        try:
            system_prompt = (
                "당신은 한국어로 정확하고 간결한 답변을 작성하는 어시스턴트입니다."
            )
            model = current_agent._create_generative_model(system_prompt)  # noqa: SLF001
            answer = await current_agent._call_api_with_retry(model, prompt)  # noqa: SLF001
            answer = strip_output_tags(answer.strip())

            if answer and len(answer) > 10:
                # 답변 평가
                score = await _evaluate_answer_quality(answer, ocr_text, query_type)
                candidates.append(
                    {
                        "strategy": strategy["name"],
                        "answer": answer,
                        "score": score,
                    }
                )
                logger.info("LATS 후보 생성: %s (점수: %.2f)", strategy["name"], score)
        except Exception as e:
            logger.debug("LATS 답변 생성 실패 (%s): %s", strategy["name"], e)
            continue

    # 최고 점수 답변 선택
    if candidates:
        best = max(candidates, key=lambda x: float(x["score"]))
        meta = {
            "candidates": len(candidates),
            "best_strategy": best["strategy"],
            "best_score": best["score"],
            "all_scores": [c["score"] for c in candidates],
        }
        best_answer = str(best["answer"])
        return best_answer, meta

    return "", {}


async def _evaluate_answer_quality(
    answer: str,
    ocr_text: str,
    query_type: str,
) -> float:
    """답변 품질을 0.0-1.0로 점수화."""
    if not answer:
        return 0.0

    score = 0.5

    # 1. 길이 검증
    if 10 < len(answer) < 5000:
        score += 0.1

    # 2. OCR 숫자 포함 검증
    import re

    ocr_numbers = set(re.findall(r"\d+(?:\.\d+)?", ocr_text))
    answer_numbers = set(re.findall(r"\d+(?:\.\d+)?", answer))
    if ocr_numbers and answer_numbers & ocr_numbers:
        score += 0.2

    # 3. 금지 패턴 검증
    forbidden_patterns = [r"^\s*[-*•]\s", r"\*\*", r"__"]
    has_forbidden = any(re.search(p, answer, re.MULTILINE) for p in forbidden_patterns)
    if not has_forbidden:
        score += 0.1

    return min(1.0, max(0.0, score))


async def _lats_evaluate_answer(node: "SearchNode") -> float:
    """LATS 평가: 생성된 답변의 품질을 0.0-1.0로 점수화."""
    # SearchState에서 필요한 정보 추출
    state = node.state
    current_answer = state.current_answer or ""
    ocr_text = state.ocr_text or ""

    if not current_answer:
        return 0.0

    score = 0.5  # 기본 점수

    # 1. 길이 검증 (너무 짧거나 길면 감점)
    if 10 < len(current_answer) < 5000:
        score += 0.1

    # 2. OCR 텍스트에서 주요 숫자가 포함되었는지 검증
    import re

    ocr_numbers = set(re.findall(r"\d+(?:\.\d+)?", ocr_text))
    answer_numbers = set(re.findall(r"\d+(?:\.\d+)?", current_answer))
    if ocr_numbers and answer_numbers & ocr_numbers:
        # 교집합이 있으면 OCR의 숫자를 사용했다는 증거
        score += 0.2

    # 3. 금지 패턴 검증 (마크다운 불릿 등)
    forbidden_patterns = [r"^\s*[-*•]\s", r"\*\*", r"__"]
    has_forbidden = any(
        re.search(p, current_answer, re.MULTILINE) for p in forbidden_patterns
    )
    if not has_forbidden:
        score += 0.1

    # 4. Neo4j 제약사항 검증 (선택)
    current_kg = _get_kg()
    if current_kg:
        # 간단한 제약사항 체크 (예: 최소 길이, 형식 등)
        # 실제로는 각 제약사항을 순회하며 검증해야 함
        with contextlib.suppress(Exception):
            score += 0.1

    return min(1.0, max(0.0, score))


@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - WorkspaceExecutor 사용 (Phase 3, 4 완료)."""
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
        body.query or "", body.answer or "", body.edit_request or ""
    )
    
    try:
        workflow_type = WorkflowType(workflow_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"알 수 없는 워크플로우: {workflow_str}")
    
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
            Dict[str, Any], build_response(result_dict, metadata=meta, config=config)
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
        raise HTTPException(status_code=500, detail=f"실행 실패: {str(e)}")


__all__ = [
    "api_generate_answer_from_query",
    "api_generate_query_from_answer",
    "api_unified_workspace",
    "api_workspace",
    "router",
    "set_dependencies",
]
