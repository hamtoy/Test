"""Dynamic Template Generator with Neo4j Integration.

하위 호환성을 위해 이 모듈을 유지합니다.
실제 구현은 src.qa.prompts.template_manager로 이동했습니다.

Usage (기존 방식 계속 지원):
    from src.processing.template_generator import DynamicTemplateGenerator

권장 사용:
    from src.qa.prompts import DynamicTemplateGenerator
"""

from __future__ import annotations

# Re-export from new location for backward compatibility
from src.qa.prompts.template_manager import (
    REPO_ROOT,
    TEMPLATE_DIR,
    USER_TARGET_TEMPLATE,
    DynamicTemplateGenerator,
)

__all__ = [
    "REPO_ROOT",
    "TEMPLATE_DIR",
    "USER_TARGET_TEMPLATE",
    "DynamicTemplateGenerator",
]
