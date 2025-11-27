#!/usr/bin/env python3
"""Auto-migrate deprecated imports to new paths."""

import argparse
import difflib
import fnmatch
import re
import sys
from pathlib import Path

IMPORT_MAPPINGS = {
    # Old import pattern -> New import
    r"from src\.utils import": "from src.infra.utils import",
    r"from src\.logging_setup import": "from src.infra.logging import",
    r"from src\.constants import": "from src.config.constants import",
    r"from src\.exceptions import": "from src.config.exceptions import",
    r"from src\.models import": "from src.core.models import",
    r"from src\.budget_tracker import": "from src.infra.budget import",
    r"from src\.neo4j_utils import": "from src.infra.neo4j import",
    r"from src\.health_check import": "from src.infra.health import",
    r"from src\.worker import": "from src.infra.worker import",
    r"from src\.gemini_model_client import": "from src.llm.gemini import",
    r"from src\.data_loader import": "from src.processing.loader import",
    r"from src\.semantic_analysis import": "from src.analysis.semantic import",
    r"from src\.qa_rag_system import": "from src.qa.rag_system import",
    r"from src\.caching_layer import": "from src.caching.layer import",
    r"from src\.smart_autocomplete import": "from src.features.autocomplete import",
    r"from src\.graph_enhanced_router import": "from src.routing.graph_router import",
}


class MigrationResult:
    """Result of migrating a single file."""

    def __init__(
        self,
        filepath: Path,
        changes: list[tuple[str, str]],
        original_content: str,
        new_content: str,
    ):
        self.filepath = filepath
        self.changes = changes
        self.original_content = original_content
        self.new_content = new_content

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0


def should_exclude(filepath: Path, exclude_patterns: list[str]) -> bool:
    """Check if a file should be excluded based on patterns."""
    filepath_str = str(filepath)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(filepath_str, pattern):
            return True
        if fnmatch.fnmatch(filepath.name, pattern):
            return True
    return False


def migrate_file(
    filepath: Path, fix: bool = False, exclude_patterns: list[str] | None = None
) -> MigrationResult | None:
    """Migrate imports in a single file.

    Returns MigrationResult with details about changes, or None if file should be skipped.
    """
    if exclude_patterns is None:
        exclude_patterns = []

    if should_exclude(filepath, exclude_patterns):
        return None

    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

    changes: list[tuple[str, str]] = []
    new_content = content

    for old_pattern, new_import in IMPORT_MAPPINGS.items():
        if re.search(old_pattern, content):
            changes.append((old_pattern, new_import))
            # Always compute new_content for diff generation
            new_content = re.sub(old_pattern, new_import, new_content)

    if fix and changes:
        filepath.write_text(new_content, encoding="utf-8")

    return MigrationResult(filepath, changes, content, new_content)


def generate_diff(result: MigrationResult) -> str:
    """Generate unified diff for a migration result."""
    original_lines = result.original_content.splitlines(keepends=True)
    new_lines = result.new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{result.filepath}",
        tofile=f"b/{result.filepath}",
    )
    return "".join(diff)


def collect_files(path: Path, exclude_patterns: list[str] | None = None) -> list[Path]:
    """Collect Python files to process."""
    if exclude_patterns is None:
        exclude_patterns = []

    if path.is_file():
        if not should_exclude(path, exclude_patterns):
            return [path]
        return []

    files = []
    for filepath in path.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        if not should_exclude(filepath, exclude_patterns):
            files.append(filepath)

    return files


def main(args: list[str] | None = None) -> int:
    """Main entry point for the migration tool."""
    parser = argparse.ArgumentParser(
        description="Migrate deprecated imports to new paths"
    )
    parser.add_argument(
        "--check", action="store_true", help="Dry run, show what would be changed"
    )
    parser.add_argument("--fix", action="store_true", help="Apply changes to files")
    parser.add_argument("--path", default=".", help="Path to scan (file or directory)")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Exclude files matching pattern (can be used multiple times)",
    )
    parser.add_argument(
        "--show-diff",
        action="store_true",
        help="Show unified diff of changes",
    )

    parsed_args = parser.parse_args(args)

    # Default to check mode if neither check nor fix specified
    if not parsed_args.check and not parsed_args.fix:
        parsed_args.check = True

    path = Path(parsed_args.path)
    exclude_patterns = parsed_args.exclude

    files = collect_files(path, exclude_patterns)

    results: list[MigrationResult] = []
    for filepath in files:
        result = migrate_file(
            filepath, fix=parsed_args.fix, exclude_patterns=exclude_patterns
        )
        if result and result.has_changes:
            results.append(result)

    if results:
        total_files = len(results)
        total_imports = sum(len(r.changes) for r in results)

        if parsed_args.check:
            print(
                f"{total_files} file(s) would be modified, {total_imports} import(s) updated"
            )
        else:
            print(f"{total_files} file(s) modified, {total_imports} import(s) updated")

        for result in results:
            print(f"\n📄 {result.filepath}")
            for old_pattern, new_import in result.changes:
                print(f"   {old_pattern} → {new_import}")

            if parsed_args.show_diff:
                diff = generate_diff(result)
                if diff:
                    print("\n" + diff)

        if parsed_args.fix:
            print(f"\n✅ Fixed {total_imports} imports in {total_files} files")

        return 0
    else:
        print("✅ No deprecated imports found")
        return 0


if __name__ == "__main__":
    sys.exit(main())
