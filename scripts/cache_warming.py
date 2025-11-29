"""서비스 시작 시 자주 사용되는 템플릿을 미리 캐시에 로드.

캐시 워밍을 통해 첫 번째 요청의 응답 시간을 개선합니다.

사용법:
    # 기본 (high 우선순위만)
    python scripts/cache_warming.py

    # 모든 우선순위
    python scripts/cache_warming.py all

    # 특정 우선순위
    python scripts/cache_warming.py medium
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 우선순위별 템플릿 (실제 사용 빈도 기반)
PRIORITY_TEMPLATES: dict[str, list[str]] = {
    "high": [
        "system/text_image_qa_explanation_system.j2",  # 가장 많이 사용
        "system/text_image_qa_summary_system.j2",  # 두번째
        "eval/text_image_qa_compare_eval.j2",  # 평가용
        "rewrite/text_image_qa_rewrite_system.j2",  # 리라이트용
    ],
    "medium": [
        "system/text_image_qa_reasoning_system.j2",
        "system/text_image_qa_global_system.j2",
    ],
    "low": [
        "user/text_image_qa_generic_user.j2",
        "user/text_image_qa_target_user.j2",
        "fact/text_image_qa_fact_check.j2",
    ],
}


@dataclass
class WarmingStats:
    """캐시 워밍 통계."""

    total: int = 0
    success: int = 0
    failed: int = 0
    not_found: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """성공률 계산."""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100


class CacheWarmer:
    """캐시 워밍 실행기."""

    def __init__(self, template_dir: Path | None = None) -> None:
        """CacheWarmer 초기화.

        Args:
            template_dir: 템플릿 디렉토리 경로 (기본값: 프로젝트 루트의 templates/)
        """
        if template_dir is None:
            project_root = Path(__file__).resolve().parents[1]
            template_dir = project_root / "templates"

        self.template_dir = template_dir
        self.stats = WarmingStats()
        self._env: Any = None

    def _get_jinja_env(self) -> Any:
        """Jinja2 환경 초기화 (지연 로딩)."""
        if self._env is None:
            from jinja2 import Environment, FileSystemLoader

            self._env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=True,
            )
        return self._env

    async def warm_all(self, priority: str = "high") -> WarmingStats:
        """우선순위별 캐시 워밍 실행.

        Args:
            priority: "high", "medium", "low" 또는 "all"

        Returns:
            워밍 통계
        """
        start_time = time.time()

        # 워밍할 템플릿 결정
        if priority == "all":
            templates = [
                t for template_list in PRIORITY_TEMPLATES.values() for t in template_list
            ]
        else:
            templates = PRIORITY_TEMPLATES.get(priority, [])

        if not templates:
            print(f"⚠️ No templates found for priority: {priority}")
            return self.stats

        self.stats.total = len(templates)

        print(f"🔥 Cache Warming Started")
        print(f"   Priority: {priority}")
        print(f"   Templates: {len(templates)}")
        print()

        if not self.template_dir.exists():
            print(f"❌ Templates directory not found: {self.template_dir}")
            self.stats.failed = len(templates)
            return self.stats

        for template_path in templates:
            await self._warm_template(template_path)

        self.stats.duration_ms = (time.time() - start_time) * 1000

        self._print_summary()
        return self.stats

    async def _warm_template(self, template_path: str) -> bool:
        """단일 템플릿 워밍.

        Args:
            template_path: 템플릿 경로

        Returns:
            성공 여부
        """
        from jinja2 import TemplateNotFound

        try:
            env = self._get_jinja_env()
            # 템플릿 로드 (컴파일되어 캐시됨)
            env.get_template(template_path)
            print(f"  ✓ Warmed: {template_path}")
            self.stats.success += 1
            return True

        except TemplateNotFound:
            print(f"  ⚠ Not found: {template_path}")
            self.stats.not_found += 1
            self.stats.errors.append(f"Template not found: {template_path}")
            return False

        except Exception as e:
            print(f"  ✗ Failed: {template_path} - {e}")
            self.stats.failed += 1
            self.stats.errors.append(f"Error warming {template_path}: {e}")
            return False

    def _print_summary(self) -> None:
        """결과 요약 출력."""
        print()
        print("=" * 50)
        print("📊 Cache Warming Summary")
        print("=" * 50)
        print(f"Total:     {self.stats.total}")
        print(f"Success:   {self.stats.success}")

        if self.stats.not_found > 0:
            print(f"Not Found: {self.stats.not_found}")

        if self.stats.failed > 0:
            print(f"Failed:    {self.stats.failed}")

        print(f"Duration:  {self.stats.duration_ms:.0f}ms")

        success_rate = self.stats.success_rate

        if success_rate == 100:
            print("\n✅ All templates warmed successfully!")
        elif success_rate >= 80:
            print(f"\n⚠️  Some templates failed ({success_rate:.0f}% success)")
        else:
            print(f"\n❌ Many templates failed ({success_rate:.0f}% success)")


async def warm_cache(priority: str = "high") -> WarmingStats:
    """캐시 워밍 실행.

    Args:
        priority: 우선순위 레벨 ("high", "medium", "low", "all")

    Returns:
        워밍 통계
    """
    warmer = CacheWarmer()
    return await warmer.warm_all(priority=priority)


def main() -> int:
    """메인 진입점."""
    # 우선순위 인자 처리
    priority = sys.argv[1] if len(sys.argv) > 1 else "high"

    if priority not in ("high", "medium", "low", "all"):
        print(f"❌ Invalid priority: {priority}")
        print("   Valid options: high, medium, low, all")
        return 1

    try:
        stats = asyncio.run(warm_cache(priority=priority))

        # 80% 미만 성공률이면 경고 반환
        if stats.success_rate < 80:
            return 1
        return 0

    except KeyboardInterrupt:
        print("\n⚠️ Cache warming interrupted")
        return 130
    except Exception as e:
        print(f"❌ Cache warming failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
