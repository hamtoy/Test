#!/usr/bin/env python3
"""
v3.0 마이그레이션 준비도 검증 스크립트.

This script scans the entire codebase to detect deprecated shim imports
and generates a readiness report for v3.0 migration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

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

# Skip patterns for directories
SKIP_DIRS = [".venv", "venv", "__pycache__", ".git", "build", "dist", "*.egg-info"]


def should_skip_path(filepath: Path) -> bool:
    """Check if a file path should be skipped.

    Args:
        filepath: Path to check.

    Returns:
        True if the path should be skipped.
    """
    filepath_str = str(filepath)
    return any(skip in filepath_str for skip in SKIP_DIRS)


def scan_entire_codebase() -> dict[str, list[tuple[str, int]]]:
    """
    Scan entire codebase for shim import usages.

    Returns:
        Dictionary mapping shim file name to list of (filepath, line_number) tuples.
    """
    results: dict[str, list[tuple[str, int]]] = {}

    for py_file in Path(".").rglob("*.py"):
        if should_skip_path(py_file):
            continue

        # Skip the shim files themselves
        if py_file.name in SHIM_FILES and str(py_file).startswith("src/"):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError):
            continue

        for line_num, line in enumerate(content.split("\n"), 1):
            for shim in SHIM_FILES:
                module = shim.replace(".py", "")
                # Match patterns:
                # from src.models import ...
                # from src import models
                # import src.models
                patterns = [
                    rf"\bfrom\s+src\.{module}\s+import\b",
                    rf"\bfrom\s+src\s+import\s+{module}\b",
                    rf"\bimport\s+src\.{module}\b",
                ]

                for pattern in patterns:
                    if re.search(pattern, line):
                        results.setdefault(shim, []).append((str(py_file), line_num))
                        break  # Only count once per line per shim

    return results


def generate_readiness_report(results: dict[str, list[tuple[str, int]]]) -> int:
    """Generate migration readiness report.

    Args:
        results: Dictionary of shim usages from scan_entire_codebase.

    Returns:
        Exit code (0 for ready, 1 for blocked).
    """
    total_usages = sum(len(v) for v in results.values())

    if total_usages == 0:
        print("✅ v3.0 Ready: No deprecated imports found!")
        print("\n" + "=" * 70)
        print("All imports are using the new package-based structure.")
        print("The codebase is ready for v3.0 migration.")
        print("=" * 70)
        return 0

    print(f"❌ v3.0 Blocked: {total_usages} deprecated import(s) found\n")

    # Sort by usage count (most used first)
    sorted_shims = sorted(results.items(), key=lambda x: len(x[1]), reverse=True)

    for shim, usages in sorted_shims:
        if not usages:
            continue

        print(f"\n{shim}: {len(usages)} usage(s)")
        for filepath, line_num in usages[:5]:  # Top 5
            print(f"  - {filepath}:{line_num}")

        if len(usages) > 5:
            print(f"  ... and {len(usages) - 5} more")

    print("\n" + "=" * 70)
    print("To fix these issues, run:")
    print("  python scripts/migrate_imports.py --fix")
    print("\nOr manually update imports to use package paths:")
    print("  src.models -> src.core.models")
    print("  src.utils -> src.infra.utils")
    print("  src.config -> src.config.settings")
    print("  etc.")
    print("=" * 70)

    return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    print("=" * 70)
    print("v3.0 Migration Readiness Check")
    print("=" * 70)
    print("\nScanning codebase for deprecated shim imports...")

    results = scan_entire_codebase()
    return generate_readiness_report(results)


if __name__ == "__main__":
    import sys

    sys.exit(main())
