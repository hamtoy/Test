# mypy: allow-untyped-decorators
"""메트릭 엔드포인트.

엔드포인트:
- GET /metrics - Prometheus 메트릭
- GET /api/analytics/current - 실시간 메트릭
- GET /api/metrics/performance - 성능 메트릭
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["metrics"])

ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"


@router.get("/api/metrics/performance")
async def get_performance_metrics(
    operation: str | None = None,
) -> dict[str, dict[str, float]]:
    """실시간 성능 메트릭 조회.

    Args:
        operation: 특정 작업 필터 (None이면 전체)

    Returns:
        작업별 성능 통계
    """
    from src.infra.performance_tracker import get_tracker

    tracker = get_tracker()
    return tracker.get_stats(operation=operation)


if ENABLE_METRICS:

    @router.get("/metrics")
    async def metrics_endpoint() -> Response:
        """Prometheus metrics endpoint."""
        from src.monitoring.metrics import get_metrics

        return Response(content=get_metrics(), media_type="text/plain")

    @router.get("/api/analytics/current")
    async def current_metrics() -> dict[str, Any]:
        """실시간 메트릭 조회."""
        from src.analytics.dashboard import UsageDashboard

        dashboard = UsageDashboard()
        today_stats = dashboard.get_today_stats()

        return {
            "today": {
                "sessions": today_stats["sessions"],
                "cost": today_stats["cost"],
                "cache_hit_rate": today_stats["cache_hit_rate"],
            },
            "this_week": {
                "total_cost": dashboard.get_week_total_cost(),
                "avg_quality": dashboard.get_week_avg_quality(),
            },
        }


__all__ = ["router"]
