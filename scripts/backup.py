"""
데이터 백업/복원 도구

중요 데이터의 백업 및 복원을 자동화합니다.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from datetime import datetime
from pathlib import Path

BACKUP_ITEMS = [
    "data/outputs/",
    "cache_stats.jsonl",
    "checkpoint.jsonl",
    ".env",
]


def backup(
    output: str | None = None,
    exclude_env: bool = False,
) -> None:
    """데이터 백업"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output or f"backup_{timestamp}.tar.gz"

    items_to_backup = BACKUP_ITEMS.copy()
    if exclude_env:
        items_to_backup = [item for item in items_to_backup if item != ".env"]

    print(f"📦 백업 시작: {backup_file}")

    with tarfile.open(backup_file, "w:gz") as tar:
        for item in items_to_backup:
            path = Path(item)
            if path.exists():
                tar.add(item)
                print(f"  ✓ {item}")
            else:
                print(f"  ⊘ {item} (없음)")

    if Path(backup_file).exists():
        size_mb = Path(backup_file).stat().st_size / (1024**2)
        print(f"\n✅ 백업 완료: {backup_file} ({size_mb:.2f}MB)")
    else:
        print("\n❌ 백업 파일 생성 실패")


def restore(
    backup_file: str,
    dry_run: bool = False,
) -> None:
    """데이터 복원"""
    backup_path = Path(backup_file)
    if not backup_path.exists():
        print(f"❌ 백업 파일을 찾을 수 없습니다: {backup_file}")
        sys.exit(1)

    print(f"📂 백업 파일: {backup_file}")

    with tarfile.open(backup_file, "r:gz") as tar:
        members = tar.getmembers()
        print(f"\n📋 포함된 파일 ({len(members)}개):")
        for member in members[:10]:
            print(f"  - {member.name}")
        if len(members) > 10:
            print(f"  ... 외 {len(members) - 10}개")

        if dry_run:
            print("\n🔍 Dry-run 모드: 실제 복원 안 함")
            return

        confirm = input("\n복원하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("취소됨")
            return

        tar.extractall()
        print("\n✅ 복원 완료")


def clean(days: int = 30) -> None:
    """오래된 백업 삭제"""
    backup_files = list(Path(".").glob("backup_*.tar.gz"))
    deleted = 0

    for file in backup_files:
        age_days = (datetime.now() - datetime.fromtimestamp(file.stat().st_mtime)).days
        if age_days > days:
            file.unlink()
            print(f"  🗑️  {file.name} (생성: {age_days}일 전)")
            deleted += 1

    if deleted == 0:
        print("삭제할 오래된 백업 없음")
    else:
        print(f"\n✅ {deleted}개 백업 삭제됨")


def main() -> None:
    parser = argparse.ArgumentParser(description="백업/복원 도구")
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령")

    # backup 명령
    backup_parser = subparsers.add_parser("backup", help="데이터 백업")
    backup_parser.add_argument("--output", type=str, help="백업 파일 경로")
    backup_parser.add_argument(
        "--exclude-env",
        action="store_true",
        help=".env 파일 제외",
    )

    # restore 명령
    restore_parser = subparsers.add_parser("restore", help="데이터 복원")
    restore_parser.add_argument("backup_file", type=str, help="백업 파일 경로")
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 복원 안 함",
    )

    # clean 명령
    clean_parser = subparsers.add_parser("clean", help="오래된 백업 삭제")
    clean_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="삭제 기준 일수 (기본: 30일)",
    )

    args = parser.parse_args()

    if args.command == "backup":
        backup(output=args.output, exclude_env=args.exclude_env)
    elif args.command == "restore":
        restore(backup_file=args.backup_file, dry_run=args.dry_run)
    elif args.command == "clean":
        clean(days=args.days)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
