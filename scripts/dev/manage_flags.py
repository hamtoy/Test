#!/usr/bin/env python
"""Feature Flag 관리 CLI - CLI for managing feature flags."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infra.feature_flags import FeatureFlags


def print_usage() -> None:
    """Print usage information."""
    print(
        """
Feature Flag 관리 CLI

Usage:
    python scripts/manage_flags.py <command> [arguments]

Commands:
    list                    모든 플래그 목록 표시
    enable <flag_name>      플래그 활성화
    disable <flag_name>     플래그 비활성화
    rollout <flag_name> <percent>   롤아웃 비율 조정 (0-100)
    show <flag_name>        플래그 상세 정보 표시

Examples:
    python scripts/manage_flags.py list
    python scripts/manage_flags.py enable smart_caching
    python scripts/manage_flags.py rollout smart_caching 50
    """
    )


def cmd_list() -> None:
    """List all feature flags."""
    flags = FeatureFlags()

    if not flags.flags:
        print("📋 등록된 플래그가 없습니다.")
        return

    print("\n📋 Feature Flags 목록\n")
    print("-" * 60)

    for name, config in flags.flags.items():
        status = "✓" if config.get("enabled", False) else "✗"
        rollout = config.get("rollout_percent", 100)
        envs = ", ".join(config.get("environments", []))
        desc = config.get("description", "설명 없음")

        print(f"{status} {name}: {desc}")
        print(f"   롤아웃: {rollout}% | 환경: {envs}")
        print()


def cmd_enable(flag_name: str) -> None:
    """Enable a feature flag."""
    flags = FeatureFlags()

    if flag_name not in flags.flags:
        print(f"❌ 플래그 없음: {flag_name}")
        return

    if flags.enable_flag(flag_name):
        print(f"✓ {flag_name} 활성화 완료")
    else:
        print(f"❌ {flag_name} 활성화 실패")


def cmd_disable(flag_name: str) -> None:
    """Disable a feature flag."""
    flags = FeatureFlags()

    if flag_name not in flags.flags:
        print(f"❌ 플래그 없음: {flag_name}")
        return

    if flags.disable_flag(flag_name):
        print(f"✓ {flag_name} 비활성화 완료")
    else:
        print(f"❌ {flag_name} 비활성화 실패")


def cmd_rollout(flag_name: str, percent_str: str) -> None:
    """Set rollout percentage for a flag."""
    try:
        percent = int(percent_str)
    except ValueError:
        print("❌ 롤아웃 비율은 숫자여야 합니다.")
        return

    if not 0 <= percent <= 100:
        print("❌ 0-100 사이 값을 입력하세요.")
        return

    flags = FeatureFlags()

    if flag_name not in flags.flags:
        print(f"❌ 플래그 없음: {flag_name}")
        return

    if flags.set_rollout_percent(flag_name, percent):
        print(f"✓ {flag_name} 롤아웃: {percent}%")
    else:
        print("❌ 롤아웃 설정 실패")


def cmd_show(flag_name: str) -> None:
    """Show detailed information about a flag."""
    flags = FeatureFlags()

    if flag_name not in flags.flags:
        print(f"❌ 플래그 없음: {flag_name}")
        return

    config = flags.flags[flag_name]
    print(f"\n📌 {flag_name}\n")
    print("-" * 40)
    print(json.dumps(config, indent=2, ensure_ascii=False))


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == "list":
        cmd_list()
    elif command == "enable":
        if len(sys.argv) < 3:
            print("❌ 플래그 이름을 입력하세요.")
            return
        cmd_enable(sys.argv[2])
    elif command == "disable":
        if len(sys.argv) < 3:
            print("❌ 플래그 이름을 입력하세요.")
            return
        cmd_disable(sys.argv[2])
    elif command == "rollout":
        if len(sys.argv) < 4:
            print("❌ 사용법: rollout <flag_name> <percent>")
            return
        cmd_rollout(sys.argv[2], sys.argv[3])
    elif command == "show":
        if len(sys.argv) < 3:
            print("❌ 플래그 이름을 입력하세요.")
            return
        cmd_show(sys.argv[2])
    else:
        print(f"❌ 알 수 없는 명령: {command}")
        print_usage()


if __name__ == "__main__":
    main()
