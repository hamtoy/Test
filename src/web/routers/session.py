# mypy: allow-untyped-decorators
"""세션 관리 엔드포인트.

엔드포인트:
- GET /api/session - 세션 정보 조회
- DELETE /api/session - 세션 종료
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from src.web.session import SessionManager

router = APIRouter(prefix="/api", tags=["session"])

# Module-level session manager (set by set_dependencies)
_session_manager: SessionManager | None = None


def set_dependencies(session_manager: SessionManager) -> None:
    """Set dependencies for session router."""
    global _session_manager
    _session_manager = session_manager


def _get_session_manager() -> SessionManager:
    """Get session manager, raising error if not set."""
    if _session_manager is None:
        raise RuntimeError(
            "Session router not initialized. Call set_dependencies first."
        )
    return _session_manager


@router.get("/session")
async def get_session(request: Request) -> dict[str, Any]:
    """현재 세션 정보를 조회합니다."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="세션을 초기화할 수 없습니다.")
    session_manager = _get_session_manager()
    return session_manager.serialize(session)


@router.delete("/session")
async def delete_session(request: Request) -> dict[str, Any]:
    """현재 세션을 종료합니다."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="세션을 초기화할 수 없습니다.")
    session_manager = _get_session_manager()
    session_manager.destroy(session.session_id)
    return {"cleared": True}


__all__ = ["router", "set_dependencies"]
