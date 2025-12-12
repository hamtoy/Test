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
from typing import Any, TypeAlias, cast

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

_DictStrAny: TypeAlias = dict[str, Any]
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


def _resolve_batch_types(body: GenerateQARequest) -> list[str]:
    batch_types = body.batch_types or QA_BATCH_TYPES
    if body.mode == "batch_three" and body.batch_types is None:
        batch_types = QA_BATCH_TYPES_THREE
    if not batch_types:
        raise HTTPException(status_code=400, detail="batch_types이 비어 있습니다.")
    return list(batch_types)


def _fallback_pair(qtype: str, exc: Exception) -> dict[str, Any]:
    logger.error("%s 생성 실패: %s", qtype, exc)
    return {
        "type": qtype,
        "query": _GENERATION_FAILED_QUERY,
        "answer": f"일시적 오류: {str(exc)[:100]}",
    }


async def _generate_first_pair(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
) -> tuple[dict[str, Any], str]:
    single_timeout = _get_config().qa_single_timeout
    try:
        pair = await asyncio.wait_for(
            generate_single_qa_with_retry(agent, ocr_text, qtype),
            timeout=single_timeout,
        )
        return pair, pair.get("query", "")
    except Exception as exc:  # noqa: BLE001
        return _fallback_pair(qtype, exc), ""


def _traceback_str(exc: BaseException) -> str:
    return "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__),
    )


def _append_previous_query(pair: dict[str, Any], previous_queries: list[str]) -> None:
    query = pair.get("query")
    if query and query != _GENERATION_FAILED_QUERY:
        previous_queries.append(str(query))


async def _generate_remaining_pairs(
    agent: GeminiAgent,
    ocr_text: str,
    remaining_types: list[str],
    previous_queries: list[str],
    first_answer: str,
) -> list[dict[str, Any]]:
    batch_results = await asyncio.gather(
        *[
            generate_single_qa_with_retry(
                agent,
                ocr_text,
                qtype,
                previous_queries=previous_queries if previous_queries else None,
                explanation_answer=first_answer if qtype.startswith("target") else None,
            )
            for qtype in remaining_types
        ],
        return_exceptions=True,
    )

    results: list[dict[str, Any]] = []
    for qtype, pair in zip(remaining_types, batch_results, strict=True):
        if isinstance(pair, Exception):
            tb_str = _traceback_str(pair)
            logger.error("%s 생성 실패:\n%s", qtype, tb_str)
            results.append(_fallback_pair(qtype, pair))
            continue
        pair_dict = cast(_DictStrAny, pair)
        results.append(pair_dict)
        _append_previous_query(pair_dict, previous_queries)

    return results


async def _process_batch_request(
    body: GenerateQARequest,
    agent: GeminiAgent,
    ocr_text: str,
    start: datetime,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    batch_types = _resolve_batch_types(body)

    first_type = batch_types[0]
    first_pair, first_query = await _generate_first_pair(
        agent,
        ocr_text,
        first_type,
    )
    results.append(first_pair)

    remaining_types = batch_types[1:]
    previous_queries = [first_query] if first_query else []
    first_answer = first_pair.get("answer", "")
    if remaining_types:
        logger.info("⏳ %s 타입 동시 병렬 생성 시작", ", ".join(remaining_types))
        results.extend(
            await _generate_remaining_pairs(
                agent,
                ocr_text,
                remaining_types,
                previous_queries,
                first_answer,
            ),
        )

    duration = (datetime.now() - start).total_seconds()
    meta = APIMetadata(duration=duration)
    return cast(
        _DictStrAny,
        build_response(
            {"mode": "batch", "pairs": results},
            metadata=meta,
            config=_get_config(),
        ),
    )


async def _process_single_request(
    body: GenerateQARequest,
    agent: GeminiAgent,
    ocr_text: str,
    start: datetime,
) -> dict[str, Any]:
    if not body.qtype:
        raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
    pair = await asyncio.wait_for(
        generate_single_qa(agent, ocr_text, body.qtype),
        timeout=_get_config().qa_single_timeout,
    )
    duration = (datetime.now() - start).total_seconds()
    meta = APIMetadata(duration=duration)
    return cast(
        _DictStrAny,
        build_response(
            {"mode": "single", "pair": pair},
            metadata=meta,
            config=_get_config(),
        ),
    )


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
            return await asyncio.wait_for(
                _process_batch_request(body, current_agent, ocr_text, start),
                timeout=_get_config().qa_batch_timeout,
            )
        return await _process_single_request(body, current_agent, ocr_text, start)

    except HTTPException:
        raise
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
