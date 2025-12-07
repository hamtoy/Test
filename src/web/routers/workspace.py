"""워크스페이스 관련 엔드포인트 (메인 라우터 집합)."""
# mypy: ignore-errors

from __future__ import annotations

from fastapi import APIRouter

# Import functions that tests expect
from src.workflow.edit import edit_content  # noqa: F401
from src.workflow.inspection import inspect_answer  # noqa: F401

# Import sub-routers
from . import (
    workspace_common,
    workspace_generation,
    workspace_review,
    workspace_unified,
)

# Import LATS functions that may be needed
from .workspace_generation import (  # noqa: F401
    _evaluate_answer_quality,
    _generate_lats_answer,
    _lats_evaluate_answer,
)

# Main workspace router that aggregates all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(workspace_review.router)
router.include_router(workspace_generation.router)
router.include_router(workspace_unified.router)

# Export set_dependencies for backward compatibility
set_dependencies = workspace_common.set_dependencies

# Export key classes and constants for backward compatibility
from .workspace_common import (  # noqa: F401, E402
    DEFAULT_LATS_WEIGHTS,
    LATS_WEIGHTS_PRESETS,
    MAX_REWRITE_ATTEMPTS,
    AnswerQualityWeights,
    _difficulty_hint,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator,
)

# Export all routers and key functions for backward compatibility
__all__ = [
    "router",
    "set_dependencies",
    "workspace_common",
    "workspace_generation",
    "workspace_review",
    "workspace_unified",
    "edit_content",
    "inspect_answer",
    "_evaluate_answer_quality",
    "_generate_lats_answer",
    "_lats_evaluate_answer",
    "DEFAULT_LATS_WEIGHTS",
    "LATS_WEIGHTS_PRESETS",
    "MAX_REWRITE_ATTEMPTS",
    "AnswerQualityWeights",
]
