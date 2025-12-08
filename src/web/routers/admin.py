"""관리자용 캐시 엔드포인트 (로컬/개인용, 인증 없음)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

from fastapi import APIRouter, HTTPException

from src.qa.rule_loader import (
    clear_global_rule_cache,
    get_global_cache_info,
)

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/admin", tags=["admin"])
P = ParamSpec("P")
R = TypeVar("R")


def admin_get(path: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper for router.get."""
    return cast("Callable[[Callable[P, R]], Callable[P, R]]", router.get(path))


def admin_post(path: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Typed wrapper for router.post."""
    return cast("Callable[[Callable[P, R]], Callable[P, R]]", router.post(path))


@admin_get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """전역 RuleLoader 캐시 통계 조회."""
    try:
        cache_info = get_global_cache_info()
        logger.info(
            "Admin cache stats requested: hits=%s misses=%s",
            cache_info["hits"],
            cache_info["misses"],
        )
        return {"cache": cache_info, "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to get cache stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@admin_post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    """전역 RuleLoader 캐시 초기화."""
    try:
        clear_global_rule_cache()
        logger.warning("Global rule cache cleared via admin endpoint")
        return {"message": "Global rule cache cleared", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to clear cache: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@admin_get("/cache/health")
async def cache_health() -> dict[str, Any]:
    """캐시 히트율 기반 헬스체크."""
    cache_info = get_global_cache_info()
    hit_rate = float(cache_info.get("hit_rate") or 0.0)
    status = "ok" if hit_rate >= 0.5 else "warning"
    message = (
        "Cache healthy"
        if status == "ok"
        else "Low cache hit rate - check query patterns or increase maxsize"
    )
    return {
        "status": status,
        "hit_rate": hit_rate,
        "message": message,
        "cache": cache_info,
    }
