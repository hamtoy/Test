# mypy: allow-untyped-decorators
"""QA 생성 엔드포인트.

이 모듈은 QA 생성 API 라우터를 제공합니다.
핵심 생성 로직은 qa_gen_core 패키지에서 분리되어 있습니다.

배치 생성 흐름:
1. global_explanation 먼저 순차 생성
2. 나머지 타입 (reasoning, target_short, target_long) 동시 병렬 생성
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agent import GeminiAgent
from src.config.constants import (
    ESTIMATED_CACHE_HIT_TIME_SAVINGS,
    QA_BATCH_TYPES,
    QA_BATCH_TYPES_THREE,
)
from src.web.cache import answer_cache
from src.web.models import GenerateQARequest
from src.web.response import APIMetadata, build_response
from src.web.utils import load_ocr_text

from .qa_common import (
    _get_agent,
    _get_config,
    logger,
)

# 새로운 모듈형 QA 생성 로직
from .qa_gen_core import generate_single_qa

router = APIRouter(prefix="/api", tags=["qa-generation"])

_DICT_STR_ANY = "dict[str, Any]"
_GENERATION_FAILED_QUERY = "생성 실패"


@router.get("/qa/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics (PHASE 2B: Performance monitoring).

    Returns:
        Cache metrics including hit rate, size, and performance impact
    """
    stats = answer_cache.get_stats()
    # Add estimated time saved (use ESTIMATED_CACHE_HIT_TIME_SAVINGS constant)
    time_saved_seconds = stats["hits"] * ESTIMATED_CACHE_HIT_TIME_SAVINGS
    stats["estimated_time_saved_seconds"] = time_saved_seconds
    stats["estimated_time_saved_minutes"] = round(time_saved_seconds / 60, 2)

    return {
        "success": True,
        "data": stats,
        "message": f"Cache hit rate: {stats['hit_rate_percent']:.1f}%",
    }


@router.post("/qa/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """Clear all cached answers (PHASE 2B: Cache management).

    Returns:
        Success message with number of entries cleared
    """
    size_before = answer_cache.get_stats()["cache_size"]
    await answer_cache.clear()

    return {
        "success": True,
        "data": {"entries_cleared": size_before},
        "message": f"Cleared {size_before} cache entries",
    }


@router.post("/qa/generate")
async def api_generate_qa(body: GenerateQARequest) -> dict[str, Any]:
    """QA 생성 (배치: explanation 먼저 → 나머지 3개 동시 병렬, 단일: 타입별 생성)."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text(_get_config())

    try:
        start = datetime.now()
        if body.mode in {"batch", "batch_three"}:
            # Wrap entire batch processing in timeout
            async def _process_batch() -> dict[str, Any]:
                results: list[dict[str, Any]] = []

                batch_types = body.batch_types or QA_BATCH_TYPES
                if body.mode == "batch_three" and body.batch_types is None:
                    batch_types = QA_BATCH_TYPES_THREE
                if not batch_types:
                    raise HTTPException(
                        status_code=400,
                        detail="batch_types이 비어 있습니다.",
                    )

                first_type = batch_types[0]
                first_query: str = ""

                # 1단계: global_explanation 순차 생성
                try:
                    first_pair = await asyncio.wait_for(
                        generate_single_qa_with_retry(
                            current_agent, ocr_text, first_type
                        ),
                        timeout=_get_config().qa_single_timeout,
                    )
                    results.append(first_pair)
                    first_query = first_pair.get("query", "")
                except Exception as exc:  # noqa: BLE001
                    logger.error("%s 생성 실패: %s", first_type, exc)
                    results.append(
                        {
                            "type": first_type,
                            "query": _GENERATION_FAILED_QUERY,
                            "answer": f"일시적 오류: {str(exc)[:100]}",
                        },
                    )

                # 2단계: 나머지 타입 전부 동시 병렬 생성
                remaining_types = batch_types[1:]
                previous_queries = [first_query] if first_query else []
                # 설명문 답변 추출 (target 타입에서 중복 방지용)
                first_answer = results[0].get("answer", "") if results else ""

                if remaining_types:
                    logger.info(
                        "⏳ %s 타입 동시 병렬 생성 시작", ", ".join(remaining_types)
                    )

                    batch_results = await asyncio.gather(
                        *[
                            generate_single_qa_with_retry(
                                current_agent,
                                ocr_text,
                                qtype,
                                previous_queries=previous_queries
                                if previous_queries
                                else None,
                                explanation_answer=first_answer
                                if qtype.startswith("target")
                                else None,
                            )
                            for qtype in remaining_types
                        ],
                        return_exceptions=True,
                    )

                    for j, pair in enumerate(batch_results):
                        qtype = remaining_types[j]
                        if isinstance(pair, Exception):
                            import sys

                            tb_str = "".join(
                                traceback.format_exception(
                                    type(pair), pair, pair.__traceback__
                                )
                            )
                            sys.stderr.write(
                                f"\n[ERROR TRACEBACK] {qtype}:\n{tb_str}\n"
                            )
                            logger.error("%s 생성 실패:\n%s", qtype, tb_str)
                            results.append(
                                {
                                    "type": qtype,
                                    "query": _GENERATION_FAILED_QUERY,
                                    "answer": f"일시적 오류: {str(pair)[:100]}",
                                },
                            )
                        else:
                            results.append(cast(_DICT_STR_ANY, pair))
                            pair_dict = cast(_DICT_STR_ANY, pair)
                            if (
                                pair_dict.get("query")
                                and pair_dict.get("query") != _GENERATION_FAILED_QUERY
                            ):
                                previous_queries.append(pair_dict.get("query", ""))

                duration = (datetime.now() - start).total_seconds()
                meta = APIMetadata(duration=duration)
                return cast(
                    _DICT_STR_ANY,
                    build_response(
                        {"mode": "batch", "pairs": results},
                        metadata=meta,
                        config=_get_config(),
                    ),
                )

            return await asyncio.wait_for(
                _process_batch(),
                timeout=_get_config().qa_batch_timeout,
            )

        if not body.qtype:
            raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
        pair = await asyncio.wait_for(
            generate_single_qa(current_agent, ocr_text, body.qtype),
            timeout=_get_config().qa_single_timeout,
        )
        duration = (datetime.now() - start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            _DICT_STR_ANY,
            build_response(
                {"mode": "single", "pair": pair},
                metadata=meta,
                config=_get_config(),
            ),
        )

    except asyncio.TimeoutError:
        timeout_msg = (
            f"생성 시간 초과 ({_get_config().qa_batch_timeout if body.mode in {'batch', 'batch_three'} else _get_config().qa_single_timeout}초). "
            "다시 시도해주세요."
        )
        raise HTTPException(status_code=504, detail=timeout_msg)
    except Exception as e:
        logger.error("QA 생성 실패: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"생성 실패: {e!s}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def generate_single_qa_with_retry(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: list[str] | None = None,
    explanation_answer: str | None = None,
) -> dict[str, Any]:
    """재시도 로직이 있는 QA 생성 래퍼."""
    return await generate_single_qa(
        agent, ocr_text, qtype, previous_queries, explanation_answer
    )


# 하위 호환성을 위한 re-export
__all__ = [
    "api_generate_qa",
    "clear_cache",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "get_cache_stats",
    "router",
]
