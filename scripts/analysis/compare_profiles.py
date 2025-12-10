"""
프로파일 비교 도구

두 개의 프로파일링 결과를 비교하여 성능 회귀를 감지합니다.
- 주요 함수별 시간 비교
- 10% 이상 느려진 함수 경고
- PR 코멘트용 결과 출력
"""

from __future__ import annotations

import argparse
import pstats
import sys
from pathlib import Path
from typing import Dict


def load_profile_stats(prof_path: Path) -> Dict[str, float]:
    """프로파일 파일에서 함수별 누적 시간 추출"""
    stats = pstats.Stats(str(prof_path))
    stats.strip_dirs()

    function_times: Dict[str, float] = {}
    for (filename, lineno, funcname), (
        cc,
        nc,
        tt,
        ct,
        callers,
    ) in stats.stats.items():  # type: ignore[attr-defined]
        key = f"{filename}:{funcname}"
        function_times[key] = ct  # cumulative time

    return function_times


def compare_profiles(
    baseline_path: Path,
    current_path: Path,
    threshold: float = 0.10,
) -> bool:
    """
    두 프로파일 비교

    Args:
        baseline_path: 기준 프로파일 경로
        current_path: 현재 PR 프로파일 경로
        threshold: 경고 임계값 (기본 10%)

    Returns:
        True면 성능 저하 감지됨
    """
    baseline_stats = load_profile_stats(baseline_path)
    current_stats = load_profile_stats(current_path)

    print("=" * 70)
    print("📊 Performance Comparison Report")
    print("=" * 70)
    print(f"Baseline: {baseline_path}")
    print(f"Current:  {current_path}")
    print(f"Threshold: {threshold * 100:.0f}%")
    print()

    regressions: list[tuple[str, float, float, float]] = []
    improvements: list[tuple[str, float, float, float]] = []

    for func_name, current_time in current_stats.items():
        baseline_time = baseline_stats.get(func_name)
        if baseline_time is None or baseline_time == 0:
            continue

        change = (current_time - baseline_time) / baseline_time

        if change > threshold:
            regressions.append((func_name, baseline_time, current_time, change))
        elif change < -threshold:
            improvements.append((func_name, baseline_time, current_time, change))

    # 회귀 정렬 (가장 큰 변화 먼저)
    regressions.sort(key=lambda x: x[3], reverse=True)
    improvements.sort(key=lambda x: x[3])

    has_regressions = len(regressions) > 0

    if regressions:
        print("⚠️  PERFORMANCE REGRESSIONS DETECTED")
        print("-" * 70)
        print(f"{'Function':<40} {'Baseline':>10} {'Current':>10} {'Change':>10}")
        print("-" * 70)
        for func_name, baseline_time, current_time, change in regressions[:20]:
            func_display = func_name[:38] + ".." if len(func_name) > 40 else func_name
            print(
                f"{func_display:<40} {baseline_time * 1000:>10.2f}ms "
                f"{current_time * 1000:>10.2f}ms {change * 100:>+9.1f}%"
            )
        print()

    if improvements:
        print("✅ Performance Improvements")
        print("-" * 70)
        print(f"{'Function':<40} {'Baseline':>10} {'Current':>10} {'Change':>10}")
        print("-" * 70)
        for func_name, baseline_time, current_time, change in improvements[:10]:
            func_display = func_name[:38] + ".." if len(func_name) > 40 else func_name
            print(
                f"{func_display:<40} {baseline_time * 1000:>10.2f}ms "
                f"{current_time * 1000:>10.2f}ms {change * 100:>+9.1f}%"
            )
        print()

    if not regressions and not improvements:
        print("✅ No significant performance changes detected")
        print()

    print("=" * 70)
    if has_regressions:
        print("❌ Performance regression check FAILED")
    else:
        print("✅ Performance regression check PASSED")
    print("=" * 70)

    return has_regressions


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two profiling results")
    parser.add_argument("baseline", type=Path, help="Baseline profile file")
    parser.add_argument("current", type=Path, help="Current profile file")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="Threshold for regression warning (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with non-zero code if regression detected",
    )

    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"Error: Baseline file not found: {args.baseline}")
        sys.exit(1)

    if not args.current.exists():
        print(f"Error: Current file not found: {args.current}")
        sys.exit(1)

    has_regressions = compare_profiles(args.baseline, args.current, args.threshold)

    if args.fail_on_regression and has_regressions:
        sys.exit(1)


if __name__ == "__main__":
    main()
