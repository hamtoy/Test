# mypy: allow-untyped-decorators
"""QA 도구 엔드포인트.

엔드포인트:
- POST /api/qa/validate - QA 쌍 교차 검증
- POST /api/qa/route - 질의 유형 자동 선택
- GET /api/qa/suggest-next - 다음 질의 유형 추천
"""

from __future__ import annotations

import json as json_module
import logging
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/qa", tags=["qa-tools"])
logger = logging.getLogger(__name__)

_KG_NOT_AVAILABLE_ERROR = "Knowledge graph not available"
_NEO4J_REQUIRED_MESSAGE = "Neo4j 연결 필요"


@router.post("/validate")
async def validate_qa_pair(
    question: str,
    answer: str,
    query_type: str = "explanation",
) -> dict[str, Any]:
    """QA 쌍 교차 검증 (일관성, 근거, 규칙 준수, 참신성).

    Args:
        question: 질문 텍스트
        answer: 답변 텍스트
        query_type: 질의 유형 (explanation, reasoning 등)

    Returns:
        Validation results with issues found
    """
    from src.analysis.cross_validation import CrossValidationSystem

    from .qa_common import get_cached_kg

    try:
        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": _KG_NOT_AVAILABLE_ERROR,
                "message": _NEO4J_REQUIRED_MESSAGE,
            }

        validator = CrossValidationSystem(kg)
        result = validator.cross_validate_qa_pair(
            question=question,
            answer=answer,
            query_type=query_type,
            image_meta={},  # No image metadata for API validation
        )

        issues_count = sum(len(v) for k, v in result.items() if k.endswith("_issues"))

        logger.info(
            "QA validation completed: %d issues found",
            issues_count,
        )

        return {
            "success": True,
            "data": result,
            "message": f"{issues_count}개 이슈 발견" if issues_count else "검증 통과",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to validate QA pair: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "QA 검증 실패",
        }


@router.post("/route")
async def route_query(user_input: str) -> dict[str, Any]:
    """사용자 입력을 분석해 최적 질의 유형 자동 선택 (그래프 기반).

    Args:
        user_input: 사용자 질의 텍스트

    Returns:
        Chosen query type and routing decision
    """
    from src.routing.graph_router import GraphEnhancedRouter

    from .qa_common import get_cached_kg

    try:
        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": _KG_NOT_AVAILABLE_ERROR,
                "message": _NEO4J_REQUIRED_MESSAGE,
            }

        graph_router = GraphEnhancedRouter(kg=kg)

        # 간단 핸들러: 선택만 반환 (실제 생성은 별도 API에서)
        handlers: dict[str, Any] = {}

        result = graph_router.route_and_generate(user_input, handlers)
        chosen = result.get("choice", "unknown")

        logger.info("Query routed: input='%s...' -> %s", user_input[:50], chosen)

        return {
            "success": True,
            "data": {
                "chosen_type": chosen,
                "user_input": user_input[:200],
            },
            "message": f"질의 유형: {chosen}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to route query: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "질의 라우팅 실패",
        }


@router.get("/suggest-next")
async def suggest_next_query_type(session: str = "[]") -> dict[str, Any]:
    """다음 질의 유형 추천 (현재 세션 기반).

    Args:
        session: JSON string of current session query types

    Returns:
        Recommended next query types
    """
    from src.features.autocomplete import SmartAutocomplete

    from .qa_common import get_cached_kg

    try:
        current_session = json_module.loads(session) if session else []

        kg = get_cached_kg()
        if kg is None:
            return {
                "success": False,
                "error": _KG_NOT_AVAILABLE_ERROR,
                "message": _NEO4J_REQUIRED_MESSAGE,
            }

        autocomplete = SmartAutocomplete(kg)
        suggestions = autocomplete.suggest_next_query_type(current_session)

        logger.info(
            "Query type suggestions requested: %d suggestions",
            len(suggestions),
        )

        return {
            "success": True,
            "data": {"suggestions": suggestions},
            "message": f"{len(suggestions)}개 질의 유형 추천",
        }
    except json_module.JSONDecodeError:
        return {
            "success": False,
            "error": "Invalid session JSON",
            "message": "세션 데이터 형식 오류",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to suggest query types: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "message": "질의 유형 추천 실패",
        }


__all__ = ["router"]
