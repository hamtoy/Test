"""서비스 시작 시 자주 사용되는 템플릿을 미리 캐시에 로드

캐시 워밍을 통해 첫 번째 요청의 응답 시간을 개선합니다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 우선순위가 높은 템플릿 목록
PRIORITY_TEMPLATES = [
    "system/text_image_qa_explanation_system.j2",
    "system/text_image_qa_summary_system.j2",
    "eval/compare_three_answers.j2",
    "rewrite/enhance_answer.j2",
]


async def warm_cache() -> None:
    """캐시 워밍 실행

    템플릿 파일들을 미리 로드하여 Jinja2 환경을 준비합니다.
    실제 API 호출은 수행하지 않습니다.
    """
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound

    # 프로젝트 루트 찾기
    project_root = Path(__file__).resolve().parents[1]
    template_dir = project_root / "templates"

    if not template_dir.exists():
        print(f"⚠️ Templates directory not found: {template_dir}")
        return

    print("🔥 Starting cache warming...")

    # Jinja2 환경 설정
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )

    warmed_count = 0
    failed_count = 0

    for template_path in PRIORITY_TEMPLATES:
        try:
            # 템플릿 로드 (컴파일되어 캐시됨)
            env.get_template(template_path)
            print(f"  ✓ Warmed: {template_path}")
            warmed_count += 1
        except TemplateNotFound:
            print(f"  ⚠ Not found: {template_path}")
            failed_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {template_path} - {e}")
            failed_count += 1

    print(f"✅ Cache warming completed: {warmed_count} warmed, {failed_count} failed")


def main() -> int:
    """메인 진입점"""
    try:
        asyncio.run(warm_cache())
        return 0
    except KeyboardInterrupt:
        print("\n⚠️ Cache warming interrupted")
        return 130
    except Exception as e:
        print(f"❌ Cache warming failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
