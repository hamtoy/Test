#!/usr/bin/env python3
"""
v3.0 Shim 파일 안전 삭제 스크립트.

This script safely removes deprecated shim files with backup support
for rollback in case of issues.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

# List of 24 shim files to be removed in v3.0
SHIM_FILES = [
    "adaptive_difficulty.py",
    "advanced_context_augmentation.py",
    "cache_analytics.py",
    "caching_layer.py",
    "config.py",
    "constants.py",
    "data_loader.py",
    "dynamic_template_generator.py",
    "exceptions.py",
    "graph_enhanced_router.py",
    "graph_schema_builder.py",
    "integrated_qa_pipeline.py",
    "lats_searcher.py",
    "list_models.py",
    "logging_setup.py",
    "memory_augmented_qa.py",
    "models.py",
    "multi_agent_qa_system.py",
    "multimodal_understanding.py",
    "neo4j_utils.py",
    "qa_generator.py",
    "qa_rag_system.py",
    "qa_system_factory.py",
    "real_time_constraint_enforcer.py",
    "self_correcting_chain.py",
    "utils.py",
    "worker.py",
]

# Priority classifications for staged removal
PRIORITY_MAP = {
    "P0": [  # High usage
        "config.py",
        "qa_rag_system.py",
        "exceptions.py",
        "models.py",
    ],
    "P1": [  # Mid usage
        "constants.py",
        "utils.py",
        "logging_setup.py",
        "neo4j_utils.py",
    ],
    "P2": [  # Low usage (remaining files)
        "adaptive_difficulty.py",
        "advanced_context_augmentation.py",
        "cache_analytics.py",
        "caching_layer.py",
        "data_loader.py",
        "dynamic_template_generator.py",
        "graph_enhanced_router.py",
        "graph_schema_builder.py",
        "integrated_qa_pipeline.py",
        "lats_searcher.py",
        "list_models.py",
        "memory_augmented_qa.py",
        "multi_agent_qa_system.py",
        "multimodal_understanding.py",
        "qa_generator.py",
        "qa_system_factory.py",
        "real_time_constraint_enforcer.py",
        "self_correcting_chain.py",
        "worker.py",
    ],
}


def backup_shims(shim_files: list[str]) -> Path | None:
    """Create backup of shim files before deletion.

    Args:
        shim_files: List of shim file names to backup.

    Returns:
        Path to backup directory, or None if no files were backed up.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"backup_v3_{timestamp}")
    files_backed_up = 0

    for shim in shim_files:
        src = Path("src") / shim
        if src.exists():
            if not backup_dir.exists():
                backup_dir.mkdir(exist_ok=True)
            shutil.copy2(src, backup_dir / shim)
            print(f"✅ Backed up: {shim}")
            files_backed_up += 1

    if files_backed_up > 0:
        print(f"\n📦 Backup location: {backup_dir}")
        return backup_dir

    print("⚠️  No files to backup")
    return None


def get_files_by_priority(priority: str | None) -> list[str]:
    """Get list of files based on priority filter.

    Args:
        priority: Priority level (P0, P1, P2) or None for all files.

    Returns:
        List of shim file names.
    """
    if priority is None:
        return SHIM_FILES

    priority_upper = priority.upper()
    if priority_upper in PRIORITY_MAP:
        return PRIORITY_MAP[priority_upper]

    # If 'all' is specified, return all files
    if priority.lower() == "all":
        return SHIM_FILES

    print(f"⚠️  Unknown priority: {priority}. Valid options: P0, P1, P2, all")
    return []


def remove_shims(shim_files: list[str], dry_run: bool = True) -> int:
    """Remove shim files.

    Args:
        shim_files: List of shim file names to remove.
        dry_run: If True, only show what would be deleted.

    Returns:
        Number of files deleted.
    """
    deleted_count = 0

    for shim in shim_files:
        filepath = Path("src") / shim

        if not filepath.exists():
            print(f"⚠️  Already removed: {shim}")
            continue

        if dry_run:
            print(f"[DRY RUN] Would delete: {shim}")
        else:
            filepath.unlink()
            print(f"✅ Deleted: {shim}")
            deleted_count += 1

    return deleted_count


def update_gitignore() -> None:
    """Add backup folder pattern to .gitignore."""
    gitignore = Path(".gitignore")

    # Check if pattern already exists
    if gitignore.exists():
        content = gitignore.read_text()
        if "backup_v3_" in content:
            print("ℹ️  .gitignore already contains backup pattern")
            return

    with open(gitignore, "a") as f:
        f.write("\n# v3.0 shim backups\nbackup_v3_*/\n")

    print("✅ Updated .gitignore with backup folder pattern")


def show_summary(priority: str | None, dry_run: bool, deleted: int) -> None:
    """Show summary of the operation.

    Args:
        priority: Priority level used.
        dry_run: Whether this was a dry run.
        deleted: Number of files deleted.
    """
    print("\n" + "=" * 70)
    if dry_run:
        print("DRY RUN SUMMARY")
        print("Run with --execute to apply changes")
    else:
        print("EXECUTION SUMMARY")
        print(f"Deleted {deleted} shim file(s)")

    if priority:
        print(f"Priority: {priority.upper()}")

    print("=" * 70)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="Remove deprecated shim files for v3.0 migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, don't delete files",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete files (creates backup first)",
    )
    parser.add_argument(
        "--priority",
        choices=["P0", "P1", "P2", "p0", "p1", "p2", "all"],
        help="Only remove files of specified priority (P0=high, P1=mid, P2=low)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (not recommended)",
    )
    args = parser.parse_args()

    # Default to dry run if neither specified
    if not args.dry_run and not args.execute:
        args.dry_run = True

    # Get files to process
    shim_files = get_files_by_priority(args.priority)
    if not shim_files:
        return 1

    print("=" * 70)
    print("v3.0 Shim File Removal")
    print("=" * 70)
    print(f"\nFiles to process: {len(shim_files)}")

    if args.execute:
        # Create backup before deletion
        if not args.no_backup:
            backup_shims(shim_files)
            print()

        deleted = remove_shims(shim_files, dry_run=False)

        # Update gitignore if backup was created
        if not args.no_backup:
            update_gitignore()

        show_summary(args.priority, dry_run=False, deleted=deleted)

        if deleted > 0:
            print("\n🎉 v3.0 shim removal complete!")
            print("To rollback, copy files from the backup directory:")
            print("  cp backup_v3_*/* src/")
    else:
        remove_shims(shim_files, dry_run=True)
        show_summary(args.priority, dry_run=True, deleted=0)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
