"""
Measure mypy strict mode baseline errors.

This script runs mypy with strict=true and reports the number
and categories of errors to help plan the migration.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def run_mypy_strict() -> tuple[int, str]:
    """
    Run mypy with strict mode enabled.

    Returns:
        Tuple of (error_count, output)
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "src/",
            "--strict",
            "--ignore-missing-imports",
            "--config-file",
            "pyproject.toml",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    output = result.stdout + result.stderr

    # Count errors
    error_count = len(re.findall(r":\s*error:", output))

    return error_count, output


def categorize_errors(output: str) -> dict[str, int]:
    """
    Categorize errors by type.

    Returns:
        Dictionary mapping error category to count
    """
    categories: dict[str, int] = {}

    patterns = {
        "untyped-call": r"Call to untyped function",
        "any-generics": r"Missing type parameters|Implicit generic \"Any\"",
        "untyped-def": r"Function is missing a (type|return type) annotation",
        "implicit-reexport": r"implicit re-export|does not explicitly export",
        "untyped-decorator": r"Untyped decorator",
        "return-value": r"Incompatible return value",
        "arg-type": r"Argument .* has incompatible type",
        "misc": r"\[misc\]",
        "attr-defined": r"\[attr-defined\]",
    }

    for category, pattern in patterns.items():
        count = len(re.findall(pattern, output, re.IGNORECASE))
        if count > 0:
            categories[category] = count

    return categories


def categorize_by_file(output: str) -> dict[str, int]:
    """
    Count errors per file.

    Returns:
        Dictionary mapping file path to error count
    """
    errors_by_file: dict[str, int] = {}

    for line in output.split("\n"):
        match = re.match(r"^(src/[^:]+):\d+:\s*error:", line)
        if match:
            filepath = match.group(1)
            errors_by_file[filepath] = errors_by_file.get(filepath, 0) + 1

    return errors_by_file


def main() -> None:
    """Main entry point."""
    print("🔍 Measuring strict mode baseline...")
    print()

    error_count, output = run_mypy_strict()
    categories = categorize_errors(output)
    by_file = categorize_by_file(output)

    print("=" * 60)
    print(f"📊 Strict Mode Baseline: {error_count} errors")
    print("=" * 60)

    if categories:
        print("\n📋 Error Categories:")
        for category, count in sorted(
            categories.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {category}: {count}")

    if by_file:
        print("\n📁 Errors by File:")
        for filepath, count in sorted(
            by_file.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {filepath}: {count}")

    # Save detailed output
    report_path = Path("strict_baseline.txt")
    report_path.write_text(output)
    print(f"\n📄 Detailed output saved to: {report_path}")


if __name__ == "__main__":
    main()
