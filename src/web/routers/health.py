# mypy: allow-untyped-decorators
"""Health check and monitoring endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.infra.health import HealthChecker, HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_health_checker: HealthChecker | None = None


def set_dependencies(health_checker: HealthChecker, **_: Any) -> None:
    """Inject shared dependencies."""
    global _health_checker
    _health_checker = health_checker


@router.get("/health")
async def api_health() -> JSONResponse:
    """상세 헬스 체크."""
    if _health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")

    result = await _health_checker.check_all()
    payload = result.to_dict()
    try:
        from src.web import api as api_module

        payload["services"] = {
            "agent": api_module.agent is not None,
            "neo4j": api_module.kg is not None,
            "pipeline": api_module.pipeline is not None,
        }
    except Exception:
        payload["services"] = {}
    status_code = 200 if result.status == HealthStatus.HEALTHY else 503
    return JSONResponse(payload, status_code=status_code)


@router.get("/health/live")
async def api_liveness() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def api_readiness() -> JSONResponse:
    """Readiness probe."""
    if _health_checker is None:
        raise HTTPException(status_code=503, detail="Health checker not initialized")

    result = await _health_checker.check_all()
    if result.status == HealthStatus.UNHEALTHY:
        raise HTTPException(status_code=503, detail="Not ready")
    return JSONResponse(result.to_dict(), status_code=200)


__all__ = ["router", "set_dependencies"]
