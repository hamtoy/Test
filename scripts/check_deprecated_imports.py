#!/usr/bin/env python3
"""Pre-commit hook to check for deprecated import patterns.

This script scans Python files for deprecated import patterns and
fails if any are found. It is designed to be used as a pre-commit hook.

Usage:
    python scripts/check_deprecated_imports.py [files...]

Exit Codes:
    0: No deprecated imports found
    1: Deprecated imports found (or error)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Deprecated import patterns and their replacements
DEPRECATED_PATTERNS = {
    r"from\s+src\.utils\s+import": "src.infra.utils",
    r"from\s+src\.logging_setup\s+import": "src.infra.logging",
    r"from\s+src\.constants\s+import": "src.config.constants",
    r"from\s+src\.exceptions\s+import": "src.config.exceptions",
    r"from\s+src\.models\s+import": "src.core.models",
    r"from\s+src\.neo4j_utils\s+import": "src.infra.neo4j",
    r"from\s+src\.worker\s+import": "src.infra.worker",
    r"from\s+src\.data_loader\s+import": "src.processing.loader",
    r"from\s+src\.qa_rag_system\s+import": "src.qa.rag_system",
    r"from\s+src\.caching_layer\s+import": "src.caching.layer",
    r"from\s+src\.graph_enhanced_router\s+import": "src.routing.graph_router",
    r"from\s+src\.budget_tracker\s+import": "src.infra.budget",
    r"from\s+src\.health_check\s+import": "src.infra.health",
    r"from\s+src\.gemini_model_client\s+import": "src.llm.gemini",
    r"from\s+src\.semantic_analysis\s+import": "src.analysis.semantic",
    r"from\s+src\.smart_autocomplete\s+import": "src.features.autocomplete",
    # Also check for simple import statements
    r"import\s+src\.utils\b": "src.infra.utils",
    r"import\s+src\.logging_setup\b": "src.infra.logging",
    r"import\s+src\.constants\b": "src.config.constants",
    r"import\s+src\.exceptions\b": "src.config.exceptions",
    r"import\s+src\.models\b": "src.core.models",
    r"import\s+src\.neo4j_utils\b": "src.infra.neo4j",
    r"import\s+src\.worker\b": "src.infra.worker",
    r"import\s+src\.data_loader\b": "src.processing.loader",
    r"import\s+src\.qa_rag_system\b": "src.qa.rag_system",
    r"import\s+src\.caching_layer\b": "src.caching.layer",
    r"import\s+src\.graph_enhanced_router\b": "src.routing.graph_router",
}

# Paths to exclude from checking (shim files themselves, tests that verify shims)
EXCLUDE_PATHS = {
    "src/utils.py",
    "src/logging_setup.py",
    "src/constants.py",
    "src/exceptions.py",
    "src/models.py",
    "src/neo4j_utils.py",
    "src/worker.py",
    "src/data_loader.py",
    "src/qa_rag_system.py",
    "src/caching_layer.py",
    "src/graph_enhanced_router.py",
    "tests/test_deprecation_warnings.py",
    "tests/test_enhanced_deprecation.py",
    "scripts/migrate_imports.py",
    "scripts/check_deprecated_imports.py",
}


def should_exclude(filepath: Path) -> bool:
    """Check if a file should be excluded from deprecated import checks.

    Args:
        filepath: Path to the file to check.

    Returns:
        True if the file should be excluded, False otherwise.
    """
    path_str = str(filepath)

    # Normalize path separators
    path_str = path_str.replace("\\", "/")

    # Check if path ends with any excluded pattern
    return any(path_str.endswith(exclude) for exclude in EXCLUDE_PATHS)


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Check a single file for deprecated imports.

    Args:
        filepath: Path to the Python file to check.

    Returns:
        List of tuples: (line_number, line_content, suggested_replacement)
    """
    if should_exclude(filepath):
        return []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    issues = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, replacement in DEPRECATED_PATTERNS.items():
            if re.search(pattern, line):
                issues.append((line_num, line.strip(), replacement))

    return issues


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        0 if no deprecated imports found, 1 otherwise.
    """
    files = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files:
        # If no files specified, scan src/ directory
        src_path = Path("src")
        if src_path.exists():
            files = [str(f) for f in src_path.rglob("*.py")]

    all_issues: list[tuple[Path, int, str, str]] = []

    for file_path in files:
        if "__pycache__" in file_path:
            continue

        path = Path(file_path)
        if not path.is_file() or path.suffix != ".py":
            continue

        issues = check_file(path)
        for line_num, line, replacement in issues:
            all_issues.append((path, line_num, line, replacement))

    if all_issues:
        print("❌ Found deprecated imports:")
        print()
        for path, line_num, line, replacement in all_issues:
            print(f"  {path}:{line_num}")
            print(f"    → {line}")
            print(f"    💡 Use: from {replacement} import ...")
            print()
        print(f"Total: {len(all_issues)} deprecated import(s) found.")
        print("Run 'migrate-imports --fix' to auto-migrate these imports.")
        return 1

    print("✅ No deprecated imports found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
