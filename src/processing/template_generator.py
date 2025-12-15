"""Dynamic Template Generator with Neo4j Integration.

하위 호환성을 위해 이 모듈을 유지합니다.
실제 구현은 src.qa.prompts.template_manager로 이동했습니다.

Usage (기존 방식 계속 지원):
    from src.processing.template_generator import DynamicTemplateGenerator

권장 사용:
    from src.qa.prompts import DynamicTemplateGenerator
"""

from __future__ import annotations

# Also re-export GraphDatabase for tests that monkeypatch it
from neo4j import GraphDatabase

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
    "GraphDatabase",
]

# Forward __main__ execution to the actual implementation
if __name__ == "__main__":
    from contextlib import suppress

    from src.config.utils import require_env

    generator: DynamicTemplateGenerator | None = None
    try:
        generator = DynamicTemplateGenerator(
            neo4j_uri=require_env("NEO4J_URI"),
            neo4j_user=require_env("NEO4J_USER"),
            neo4j_password=require_env("NEO4J_PASSWORD"),
        )

        context = {
            "image_path": "sample.png",
            "has_table_chart": True,
            "session_turns": 4,
            "language_hint": "ko",
            "text_density": "high",
        }

        prompt = generator.generate_prompt_for_query_type("explanation", context)
        print("🎯 생성된 프롬프트 (앞부분):")
        print(prompt[:500], "...\n")

        test_session = {
            "turns": [
                {"type": "explanation"},
                {"type": "reasoning"},
                {"type": "target"},
                {"type": "target"},
            ],
        }
        checklist = generator.generate_validation_checklist(test_session)
        print("📝 검증 체크리스트:")
        for item in checklist:
            print(f"  [{item['query_type']}] {item['item']}")

    except Exception as e:
        print(f"❌ 실행 실패: {e}")
    finally:
        if generator is not None:
            with suppress(Exception):
                generator.close()
