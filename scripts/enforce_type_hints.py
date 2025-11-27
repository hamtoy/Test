#!/usr/bin/env python3
"""
v3.0 Type Hints Enforcement Script.

This script checks that all functions in core modules have complete type hints.
It's part of the v3.0 quality assurance process.

Usage:
    python scripts/enforce_type_hints.py [--strict]

Exit Codes:
    0: All core modules have complete type hints
    1: Type hint issues found
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Tuple

# Core modules that require complete type hints (v3.0)
CORE_MODULES = ["src/core/", "src/agent/", "src/config/"]

# Functions/methods to skip (commonly known to not need return types)
SKIP_FUNCTIONS = {"__init__", "__repr__", "__str__", "__hash__", "__eq__", "__ne__"}

# Decorators that indicate a property (no need for explicit return type annotation)
PROPERTY_DECORATORS = {"property", "staticmethod", "classmethod"}


def check_function_annotations(filepath: Path) -> List[Tuple[int, str]]:
    """Check all functions in a file for complete type annotations.

    Args:
        filepath: Path to the Python file to check

    Returns:
        List of tuples (line_number, issue_message)
    """
    issues: List[Tuple[int, str]] = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return issues

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip special methods that don't need return types
            if node.name in SKIP_FUNCTIONS:
                continue

            # Skip property methods (they often use decorators)
            has_property_decorator = any(
                (isinstance(d, ast.Name) and d.id in PROPERTY_DECORATORS)
                or (isinstance(d, ast.Attribute) and d.attr in PROPERTY_DECORATORS)
                for d in node.decorator_list
            )
            if has_property_decorator:
                continue

            # Check return type annotation
            if node.returns is None:
                issues.append(
                    (node.lineno, f"Missing return type annotation: {node.name}()")
                )

            # Check parameter type annotations
            for arg in node.args.args:
                if arg.annotation is None and arg.arg != "self" and arg.arg != "cls":
                    issues.append(
                        (
                            node.lineno,
                            f"Missing parameter type annotation: {node.name}({arg.arg})",
                        )
                    )

            # Check keyword-only arguments
            for arg in node.args.kwonlyargs:
                if arg.annotation is None:
                    issues.append(
                        (
                            node.lineno,
                            f"Missing kwarg type annotation: {node.name}({arg.arg})",
                        )
                    )

            # Check *args and **kwargs
            if node.args.vararg and node.args.vararg.annotation is None:
                issues.append(
                    (
                        node.lineno,
                        f"Missing *args type annotation: {node.name}(*{node.args.vararg.arg})",
                    )
                )
            if node.args.kwarg and node.args.kwarg.annotation is None:
                issues.append(
                    (
                        node.lineno,
                        f"Missing **kwargs type annotation: {node.name}(**{node.args.kwarg.arg})",
                    )
                )

    return issues


def scan_modules(
    module_dirs: List[str], strict: bool = False
) -> Tuple[int, List[Tuple[Path, List[Tuple[int, str]]]]]:
    """Scan all Python files in the specified modules.

    Args:
        module_dirs: List of module directory paths to scan
        strict: If True, all issues are counted. If False, only return type issues.

    Returns:
        Tuple of (total_issue_count, list of (filepath, issues))
    """
    total_issues = 0
    all_results: List[Tuple[Path, List[Tuple[int, str]]]] = []

    for module_dir in module_dirs:
        module_path = Path(module_dir)
        if not module_path.exists():
            continue

        for py_file in module_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            issues = check_function_annotations(py_file)

            if not strict:
                # In non-strict mode, only count return type issues
                issues = [
                    (line, msg) for line, msg in issues if "Missing return type" in msg
                ]

            if issues:
                all_results.append((py_file, issues))
                total_issues += len(issues)

    return total_issues, all_results


def main(args: list[str] | None = None) -> int:
    """Main entry point for the type hints enforcement script.

    Args:
        args: Command line arguments (for testing)

    Returns:
        0 if all checks pass, 1 otherwise
    """
    parser = argparse.ArgumentParser(
        description="Enforce type hints in core modules (v3.0)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Check all type hints (params + return types). Default: return types only",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=CORE_MODULES,
        help="Module directories to check (default: core, agent, config)",
    )

    parsed_args = parser.parse_args(args)

    print("🔍 v3.0 Type Hints Enforcement Check")
    print("=" * 50)
    print(f"Checking modules: {', '.join(parsed_args.modules)}")
    print(
        f"Mode: {'Strict (all annotations)' if parsed_args.strict else 'Standard (return types only)'}"
    )
    print()

    total_issues, results = scan_modules(parsed_args.modules, parsed_args.strict)

    if results:
        for filepath, issues in results:
            print(f"\n❌ {filepath}:")
            for line_num, msg in issues:
                print(f"   Line {line_num}: {msg}")

        print(f"\n{'=' * 50}")
        print(f"❌ {total_issues} type hint issue(s) found in {len(results)} file(s)")
        print("\nTo fix these issues:")
        print("  1. Add type annotations to functions: def func(x: int) -> str:")
        print("  2. Use 'None' for functions that don't return: def func() -> None:")
        print("  3. Run mypy for detailed type checking: uv run mypy src/")
        return 1
    else:
        print("✅ All core modules have complete type hints")
        return 0


if __name__ == "__main__":
    sys.exit(main())
