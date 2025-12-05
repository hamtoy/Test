# mypy: allow-untyped-decorators
"""QA 평가 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter

# Import all from qa_common
from .qa_common import *  # noqa: F403

# Explicitly import commonly used items
from .qa_common import (  # noqa: F401
    EvalExternalRequest,
    UnifiedValidator,
    _get_agent,
    _get_config,
    _get_kg,
    _get_validator_class,
    get_cached_kg,
    build_response,
    APIMetadata,
    HTTPException,
    asyncio,
    datetime,
    logger,
    cast,
)

router = APIRouter(prefix="/api", tags=["qa-evaluation"])

@router.post("/eval/external")
async def api_eval_external(body: EvalExternalRequest) -> Dict[str, Any]:
    """외부 답변 3개 평가."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    cfg = _get_config()
    ocr_text = load_ocr_text(cfg)

    try:
        from src.workflow.external_eval import evaluate_external_answers

        results = await evaluate_external_answers(
            agent=current_agent,
            ocr_text=ocr_text,
            query=body.query,
            answers=body.answers,
        )

        best = max(results, key=lambda x: x.get("score", 0))
        meta = APIMetadata(duration=0.0)
        return cast(
            Dict[str, Any],
            build_response(
                {"results": results, "best": best.get("candidate_id", "A")},
                metadata=meta,
                config=cfg,
            ),
        )

    except Exception as e:
        logger.error("평가 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"평가 실패: {str(e)}")


__all__ = [
    "api_generate_qa",
    "api_eval_external",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "router",
    "set_dependencies",
]
