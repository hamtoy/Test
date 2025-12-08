# mypy: allow-untyped-decorators
"""QA 생성 및 평가 엔드포인트 (메인 라우터 집합)."""

from __future__ import annotations

from fastapi import APIRouter

# Import sub-routers
from . import qa_common, qa_evaluation, qa_generation

# Main QA router that aggregates all sub-routers
router = APIRouter()

# Include all sub-routers
router.include_router(qa_generation.router)
router.include_router(qa_evaluation.router)

# Export set_dependencies for backward compatibility
set_dependencies = qa_common.set_dependencies

# Export commonly used items for backward compatibility
from .qa_common import (  # noqa: F401, E402
    _CachedKG,
    _get_agent,
    _get_config,
    _get_kg,
    _get_pipeline,
    _get_validator_class,
    get_cached_kg,
)

# Export helper functions for backward compatibility
from .qa_generation import (  # noqa: E402
    generate_single_qa,
    generate_single_qa_with_retry,
)

# Export all routers and key functions
__all__ = [
    "_CachedKG",
    "_get_agent",
    "_get_config",
    "_get_kg",
    "_get_pipeline",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "get_cached_kg",
    "qa_common",
    "qa_evaluation",
    "qa_generation",
    "router",
    "set_dependencies",
]
