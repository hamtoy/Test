"""로그 분석 유틸리티

구조화된 로그 파일을 분석하여 API 호출 패턴 및 통계를 추출합니다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def analyze_api_calls(log_file: Path) -> None:
    """API 호출 패턴 분석"""
    calls: list[dict[str, Any]] = []

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            if "api_call" in line:
                try:
                    data = json.loads(line)
                    calls.append(data)
                except json.JSONDecodeError:
                    continue

    if not calls:
        print("API 호출 로그가 없습니다.")
        return

    # 통계
    total_calls = len(calls)
    latencies = [c.get("latency_ms", 0) for c in calls if "latency_ms" in c]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    errors = sum(1 for c in calls if c.get("status") != "success")
    error_rate = errors / total_calls if total_calls else 0

    print("=" * 60)
    print("📊 API 호출 분석")
    print("=" * 60)
    print(f"총 호출: {total_calls}")
    print(f"평균 레이턴시: {avg_latency:.2f}ms")
    print(f"에러율: {error_rate * 100:.2f}%")

    # 모델별 통계
    models = Counter(c.get("model", "unknown") for c in calls)
    if models:
        print("\n📈 모델별 호출 수:")
        for model, count in models.most_common():
            print(f"  {model}: {count}")


def analyze_cache_events(log_file: Path) -> None:
    """캐시 이벤트 분석"""
    events: list[dict[str, Any]] = []

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            if "cache" in line.lower():
                try:
                    data = json.loads(line)
                    if data.get("event_type") == "cache":
                        events.append(data)
                except json.JSONDecodeError:
                    continue

    if not events:
        print("캐시 이벤트 로그가 없습니다.")
        return

    hits = sum(1 for e in events if e.get("hit"))
    misses = len(events) - hits
    hit_rate = hits / len(events) if events else 0

    print("=" * 60)
    print("📊 캐시 분석")
    print("=" * 60)
    print(f"총 이벤트: {len(events)}")
    print(f"히트: {hits}")
    print(f"미스: {misses}")
    print(f"히트율: {hit_rate * 100:.2f}%")


def analyze_errors(log_file: Path) -> None:
    """에러 로그 분석"""
    errors: list[str] = []

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            if "ERROR" in line or '"level":"ERROR"' in line.lower():
                errors.append(line.strip())

    print("=" * 60)
    print("❌ 에러 로그")
    print("=" * 60)
    print(f"총 에러: {len(errors)}")

    if errors:
        print("\n최근 에러 (마지막 10개):")
        for error in errors[-10:]:
            # 너무 긴 줄은 잘라서 표시
            display = error[:150] + "..." if len(error) > 150 else error
            print(f"  {display}")


def main() -> None:
    parser = argparse.ArgumentParser(description="로그 분석 유틸리티")
    parser.add_argument("log_file", type=Path, help="분석할 로그 파일")
    parser.add_argument(
        "--type",
        choices=["api", "cache", "errors", "all"],
        default="all",
        help="분석 유형 (default: all)",
    )

    args = parser.parse_args()

    if not args.log_file.exists():
        print(f"Error: 로그 파일을 찾을 수 없습니다: {args.log_file}")
        sys.exit(1)

    if args.type in ("api", "all"):
        analyze_api_calls(args.log_file)
        print()

    if args.type in ("cache", "all"):
        analyze_cache_events(args.log_file)
        print()

    if args.type in ("errors", "all"):
        analyze_errors(args.log_file)


if __name__ == "__main__":
    main()
