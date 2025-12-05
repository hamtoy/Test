"""워크스페이스 관련 엔드포인트 (메인 라우터 집합)."""
# mypy: ignore-errors

from __future__ import annotations

from fastapi import APIRouter

# Import sub-routers
from . import workspace_common, workspace_generation, workspace_review, workspace_unified

# Main workspace router that aggregates all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(workspace_review.router)
router.include_router(workspace_generation.router)
router.include_router(workspace_unified.router)

# Export set_dependencies for backward compatibility
set_dependencies = workspace_common.set_dependencies

# Export all routers and key functions for backward compatibility
__all__ = [
    "router",
    "set_dependencies",
    "workspace_common",
    "workspace_generation",
    "workspace_review",
    "workspace_unified",
]
