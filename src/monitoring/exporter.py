"""Prometheus Metrics Exporter.

FastAPI 애플리케이션에 /metrics 엔드포인트를 추가하여
Prometheus가 메트릭을 수집할 수 있도록 합니다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from src.monitoring.metrics import (
    PROMETHEUS_AVAILABLE,
    get_metrics,
    record_api_call,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """HTTP 요청/응답 메트릭을 수집하는 미들웨어."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """각 요청에 대한 메트릭을 기록합니다."""
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status = "success" if response.status_code < 400 else "error"
        except Exception:
            status = "error"
            raise
        finally:
            latency = time.perf_counter() - start_time
            # 메트릭 엔드포인트 자체는 기록에서 제외
            if request.url.path != "/metrics":
                record_api_call(
                    model="http",
                    status=status,
                    latency_seconds=latency,
                )

        return response


def add_metrics_endpoint(app: "FastAPI") -> None:
    """FastAPI 앱에 /metrics 엔드포인트를 추가합니다.

    Args:
        app: FastAPI 애플리케이션 인스턴스
    """

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Prometheus 메트릭 엔드포인트."""
        if not PROMETHEUS_AVAILABLE:
            return PlainTextResponse(
                "# Prometheus client not installed\n",
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

        metrics_data = get_metrics()
        return PlainTextResponse(
            metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    logger.info("Prometheus metrics endpoint registered at /metrics")


def setup_metrics(app: "FastAPI", *, enable_middleware: bool = True) -> None:
    """메트릭 수집을 설정합니다.

    Args:
        app: FastAPI 애플리케이션 인스턴스
        enable_middleware: 요청 메트릭 미들웨어 활성화 여부
    """
    add_metrics_endpoint(app)

    if enable_middleware:
        app.add_middleware(MetricsMiddleware)
        logger.info("Metrics middleware enabled")


__all__ = [
    "MetricsMiddleware",
    "add_metrics_endpoint",
    "setup_metrics",
]
