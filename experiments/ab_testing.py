"""
A/B 테스트 프레임워크

프롬프트, 파라미터 변경 효과 측정을 위한 프레임워크입니다.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, TypeAlias

# 테스트 함수 타입 별칭
# (test_data, config) -> Coroutine returning result dict
TestFunction: TypeAlias = Callable[
    [Any, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]


@dataclass
class Variant:
    """실험 변형

    Attributes:
        name: 변형 이름
        config: 변형에 적용할 설정
        weight: 트래픽 배분 비율 (기본: 1.0)
    """

    name: str
    config: dict[str, Any]
    weight: float = 1.0


@dataclass
class ExperimentResult:
    """실험 결과

    Attributes:
        variant_name: 변형 이름
        success: 성공 여부
        latency_ms: 응답 시간 (밀리초)
        cost_usd: 비용 (USD)
        quality_score: 품질 점수 (0-10)
        metadata: 추가 메타데이터
    """

    variant_name: str
    success: bool
    latency_ms: float
    cost_usd: float
    quality_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ABTest:
    """A/B 테스트 실행기

    여러 변형에 대해 테스트를 실행하고 결과를 비교합니다.
    """

    def __init__(self, name: str, variants: list[Variant]):
        """A/B 테스트 초기화

        Args:
            name: 실험 이름
            variants: 테스트할 변형 리스트
        """
        self.name = name
        self.variants = variants
        self.results: list[ExperimentResult] = []

    async def run(
        self,
        test_func: TestFunction,
        test_data: list[Any],
        runs_per_variant: int = 10,
    ) -> None:
        """실험 실행

        Args:
            test_func: 테스트 함수 (data, config) -> result
            test_data: 테스트 데이터 리스트
            runs_per_variant: 변형당 실행 횟수
        """
        print(f"🧪 실험 시작: {self.name}")
        print(f"  변형: {len(self.variants)}개")
        print(f"  데이터: {len(test_data)}개")
        print(f"  반복: {runs_per_variant}회/변형")

        for variant in self.variants:
            print(f"\n▶ 변형: {variant.name}")

            for i, data in enumerate(test_data[:runs_per_variant]):
                try:
                    start = time.time()
                    result = await test_func(data, variant.config)
                    latency = (time.time() - start) * 1000

                    self.results.append(
                        ExperimentResult(
                            variant_name=variant.name,
                            success=True,
                            latency_ms=latency,
                            cost_usd=result.get("cost", 0),
                            quality_score=result.get("quality", 0),
                            metadata=result,
                        )
                    )

                    print(f"  ✓ {i + 1}/{runs_per_variant}")

                except Exception as e:
                    print(f"  ✗ {i + 1}/{runs_per_variant}: {e}")
                    self.results.append(
                        ExperimentResult(
                            variant_name=variant.name,
                            success=False,
                            latency_ms=0,
                            cost_usd=0,
                            quality_score=0,
                            metadata={"error": str(e)},
                        )
                    )

        self._print_summary()

    def _print_summary(self) -> None:
        """결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 실험 결과 요약")
        print("=" * 60)

        for variant in self.variants:
            variant_results = [
                r for r in self.results if r.variant_name == variant.name
            ]

            if not variant_results:
                continue

            success_count = sum(1 for r in variant_results if r.success)
            success_rate = success_count / len(variant_results)

            successful_results = [r for r in variant_results if r.success]

            if successful_results:
                avg_latency = sum(r.latency_ms for r in successful_results) / len(
                    successful_results
                )
                avg_cost = sum(r.cost_usd for r in successful_results) / len(
                    successful_results
                )
                avg_quality = sum(r.quality_score for r in successful_results) / len(
                    successful_results
                )
            else:
                avg_latency = 0
                avg_cost = 0
                avg_quality = 0

            print(f"\n🔹 {variant.name}")
            print(f"  성공률: {success_rate * 100:.1f}%")
            print(f"  평균 레이턴시: {avg_latency:.0f}ms")
            print(f"  평균 비용: ${avg_cost:.4f}")
            print(f"  평균 품질: {avg_quality:.2f}/10")

    def get_best_variant(self, metric: str = "quality_score") -> str | None:
        """최고 성능 변형 반환

        Args:
            metric: 비교 기준 (quality_score, latency_ms, cost_usd)

        Returns:
            최고 성능 변형 이름
        """
        variant_scores: dict[str, float] = {}

        for variant in self.variants:
            variant_results = [
                r for r in self.results if r.variant_name == variant.name and r.success
            ]

            if not variant_results:
                continue

            if metric == "latency_ms":
                # 레이턴시는 낮을수록 좋음 (음수로 변환)
                score = -sum(r.latency_ms for r in variant_results) / len(
                    variant_results
                )
            elif metric == "cost_usd":
                # 비용은 낮을수록 좋음 (음수로 변환)
                score = -sum(r.cost_usd for r in variant_results) / len(variant_results)
            else:
                # 품질은 높을수록 좋음
                score = sum(r.quality_score for r in variant_results) / len(
                    variant_results
                )

            variant_scores[variant.name] = score

        if not variant_scores:
            return None

        return max(variant_scores, key=lambda k: variant_scores[k])


def run_ab_test(
    name: str,
    variants: list[Variant],
    test_func: TestFunction,
    test_data: list[Any],
    runs_per_variant: int = 10,
) -> ABTest:
    """A/B 테스트 실행 헬퍼

    Args:
        name: 실험 이름
        variants: 테스트할 변형 리스트
        test_func: 테스트 함수
        test_data: 테스트 데이터
        runs_per_variant: 변형당 실행 횟수

    Returns:
        완료된 ABTest 인스턴스
    """
    ab_test = ABTest(name, variants)
    asyncio.run(ab_test.run(test_func, test_data, runs_per_variant))
    return ab_test


__all__ = [
    "Variant",
    "ExperimentResult",
    "ABTest",
    "run_ab_test",
    "TestFunction",
]
