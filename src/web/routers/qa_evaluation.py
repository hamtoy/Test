# mypy: allow-untyped-decorators
"""QA 평가 엔드포인트.

웹앱 사용 여부: ✅ 활성 사용 중

- 웹 페이지: /eval (templates/web/eval.html)
- 프론트엔드: static/dist/chunks/eval.js
- 엔드포인트: POST /api/eval/external
- 용도: 외부 답변 3개 평가 및 최적 답변 선택
"""

from __future__ import annotations

from typing import Any, Dict, cast

from fastapi import APIRouter, HTTPException

from src.web.models import EvalExternalRequest
from src.web.response import APIMetadata, build_response
from src.web.utils import load_ocr_text

from .qa_common import (
    _get_agent,
    _get_config,
    logger,
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
    "api_eval_external",
    "router",
]
