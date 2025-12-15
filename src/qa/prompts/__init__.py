"""통합 프롬프트 패키지.

프롬프트 빌더 함수와 동적 템플릿 생성기를 한 곳에서 관리합니다.

Usage:
    from src.qa.prompts import (
        build_answer_prompt,
        build_length_constraint,
        build_extra_instructions,
        build_formatting_text,
        build_priority_hierarchy,
        DynamicTemplateGenerator,
    )
"""

from __future__ import annotations

from src.qa.prompts.builders import (
    build_answer_prompt,
    build_extra_instructions,
    build_formatting_text,
    build_length_constraint,
    build_priority_hierarchy,
)
from src.qa.prompts.template_manager import DynamicTemplateGenerator

__all__ = [
    "DynamicTemplateGenerator",
    "build_answer_prompt",
    "build_extra_instructions",
    "build_formatting_text",
    "build_length_constraint",
    "build_priority_hierarchy",
]
