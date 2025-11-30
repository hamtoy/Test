#!/usr/bin/env python3
"""Auto-migrate deprecated imports to new paths.

This script uses AST-aware parsing to only modify actual Python import statements,
preserving string literals that may contain import-like text (e.g., in test files).
"""

import argparse
import ast
import difflib
import fnmatch
import re
import sys
from pathlib import Path

# Mapping from old module path to new module path
# Used for both regex matching and AST-based replacement
IMPORT_MAPPINGS = {
    # Old module path -> New module path
    "src.utils": "src.infra.utils",
    "src.logging_setup": "src.infra.logging",
    "src.constants": "src.config.constants",
    "src.exceptions": "src.config.exceptions",
    "src.models": "src.core.models",
    "src.budget_tracker": "src.infra.budget",
    "src.neo4j_utils": "src.infra.neo4j",
    "src.health_check": "src.infra.health",
    "src.worker": "src.infra.worker",
    "src.gemini_model_client": "src.llm.gemini",
    "src.data_loader": "src.processing.loader",
    "src.semantic_analysis": "src.analysis.semantic",
    "src.qa_rag_system": "src.qa.rag_system",
    "src.caching_layer": "src.caching.layer",
    "src.smart_autocomplete": "src.features.autocomplete",
    "src.graph_enhanced_router": "src.routing.graph_router",
}


def _get_import_line_numbers(content: str) -> set[int]:
    """Parse Python code and return line numbers of actual import statements.

    This uses the AST module to identify real import statements,
    excluding string literals that may contain import-like text.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If parsing fails, return empty set (no lines will be modified)
        return set()

    import_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.add(node.lineno)
    return import_lines


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

    Uses AST parsing to identify actual import statements and only modifies those,
    preserving string literals that may contain import-like text.

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

    # Get line numbers of actual import statements using AST
    import_lines = _get_import_line_numbers(content)

    if not import_lines:
        # No valid import statements found (possibly invalid Python)
        return MigrationResult(filepath, [], content, content)

    changes: list[tuple[str, str]] = []
    lines = content.splitlines(keepends=True)
    new_lines = []

    for i, line in enumerate(lines):
        line_num = i + 1  # AST uses 1-based line numbers
        new_line = line

        # Only process lines that contain actual import statements
        if line_num in import_lines:
            for old_module, new_module in IMPORT_MAPPINGS.items():
                # Build patterns for "from X import" and "import X"
                from_pattern = rf"from {re.escape(old_module)} import"
                import_pattern = rf"^import {re.escape(old_module)}(\s|$|,)"

                if re.search(from_pattern, new_line):
                    replacement = f"from {new_module} import"
                    new_line = re.sub(from_pattern, replacement, new_line)
                    if (old_module, new_module) not in changes:
                        changes.append((old_module, new_module))
                elif re.search(import_pattern, new_line):
                    # Handle "import X" style
                    new_line = re.sub(
                        import_pattern,
                        rf"import {new_module}\1",
                        new_line,
                    )
                    if (old_module, new_module) not in changes:
                        changes.append((old_module, new_module))

        new_lines.append(new_line)

    new_content = "".join(new_lines)

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
            for old_module, new_module in result.changes:
                print(f"   from {old_module} import → from {new_module} import")

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
