#!/usr/bin/env python3
"""Mypy Progress Tracking Tool.

Tracks progress of mypy type annotation migration by comparing current
error counts against previous baselines and displaying progress metrics.

Usage:
    python scripts/track_mypy_progress.py [--baseline mypy_baseline.json]

This tool:
1. Runs mypy on the entire src/ directory
2. Compares results against a baseline file (if available)
3. Shows progress as percentage and absolute numbers
4. Highlights packages that have improved or regressed
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import LEVEL1_PACKAGES, LEVEL2_PACKAGES


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def run_mypy(target: str, config_file: str = "pyproject.toml") -> tuple[int, str]:
    """Run mypy on a target directory or file.

    Args:
        target: Path to the target directory or file
        config_file: Path to the mypy configuration file

    Returns:
        Tuple of (return_code, output)
    """
    cmd = ["mypy", target, "--config-file", config_file, "--show-error-codes"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def parse_mypy_output(output: str) -> dict[str, list[dict[str, Any]]]:
    """Parse mypy output into structured error data.

    Args:
        output: Raw mypy output string

    Returns:
        Dictionary mapping file paths to lists of error details
    """
    errors: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for line in output.strip().split("\n"):
        if ": error:" not in line:
            continue

        parts = line.split(": error:", 1)
        if len(parts) != 2:
            continue

        location = parts[0]
        message_part = parts[1].strip()

        error_code = "unknown"
        if "[" in message_part and message_part.endswith("]"):
            code_start = message_part.rfind("[")
            error_code = message_part[code_start + 1 : -1]
            message = message_part[:code_start].strip()
        else:
            message = message_part

        loc_parts = location.split(":")
        file_path = loc_parts[0]
        try:
            line_num = int(loc_parts[1]) if len(loc_parts) > 1 else 0
        except ValueError:
            line_num = 0

        errors[file_path].append(
            {
                "line": line_num,
                "code": error_code,
                "message": message,
            }
        )

    return errors


def get_package_name(file_path: str) -> str:
    """Extract package name from file path.

    Args:
        file_path: Path like 'src/agent/core.py'

    Returns:
        Package name like 'agent'
    """
    path = Path(file_path)
    parts = path.parts

    if "src" in parts:
        src_idx = parts.index("src")
        if src_idx + 1 < len(parts):
            return parts[src_idx + 1]

    return "root"


def count_errors_by_package(errors: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Count errors by package.

    Args:
        errors: Dictionary of errors by file path

    Returns:
        Dictionary mapping package names to error counts
    """
    package_counts: dict[str, int] = defaultdict(int)

    for file_path, file_errors in errors.items():
        pkg_name = get_package_name(file_path)
        package_counts[pkg_name] += len(file_errors)

    return dict(package_counts)


def load_baseline(baseline_path: Path) -> dict[str, Any] | None:
    """Load baseline report from JSON file.

    Args:
        baseline_path: Path to the baseline JSON file

    Returns:
        Baseline data dictionary or None if file doesn't exist
    """
    if not baseline_path.exists():
        return None

    try:
        return json.loads(baseline_path.read_text())
    except json.JSONDecodeError:
        return None


def print_progress_bar(current: int, total: int, width: int = 40) -> str:
    """Generate a text progress bar.

    Args:
        current: Current value
        total: Total value
        width: Width of the progress bar in characters

    Returns:
        Progress bar string
    """
    if total == 0:
        return "█" * width + " 100%"

    fixed = max(0, total - current)
    percentage = (fixed / total) * 100
    filled = int(width * (percentage / 100))
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {percentage:.1f}%"


def print_header(title: str) -> None:
    """Print a styled header.

    Args:
        title: Header text
    """
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")


def print_section(title: str) -> None:
    """Print a styled section header.

    Args:
        title: Section title
    """
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
    print("-" * 40)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Track mypy type annotation migration progress"
    )
    parser.add_argument(
        "--baseline",
        "-b",
        type=Path,
        default=Path("mypy_baseline.json"),
        help="Path to baseline JSON file (default: mypy_baseline.json)",
    )
    parser.add_argument(
        "--target",
        "-t",
        type=str,
        default="src/",
        help="Target directory to analyze (default: src/)",
    )
    args = parser.parse_args()

    print_header("📊 MYPY PROGRESS TRACKER")

    print(f"\n{Colors.BLUE}🔍 Running mypy on {args.target}...{Colors.RESET}")
    return_code, output = run_mypy(args.target)

    errors = parse_mypy_output(output)
    current_counts = count_errors_by_package(errors)
    total_current = sum(current_counts.values())

    # Load baseline if available
    baseline = load_baseline(args.baseline)

    print_section("📦 Level 2 Packages (Strict Mode)")
    for pkg in LEVEL2_PACKAGES:
        current = current_counts.get(pkg, 0)
        if baseline:
            pkg_data = baseline.get("packages", {}).get(pkg, {})
            prev = pkg_data.get("error_count", 0) if pkg_data else 0
            diff = current - prev
            if diff < 0:
                diff_str = f"{Colors.GREEN}▼{abs(diff)}{Colors.RESET}"
            elif diff > 0:
                diff_str = f"{Colors.RED}▲{diff}{Colors.RESET}"
            else:
                diff_str = "="
            status = f"{current:3d} errors {diff_str}"
        else:
            status = f"{current:3d} errors"

        if current == 0:
            print(f"  {Colors.GREEN}✅ {pkg:15}{Colors.RESET} {status}")
        else:
            print(f"  {Colors.RED}❌ {pkg:15}{Colors.RESET} {status}")

    print_section("📦 Level 1 Packages")
    for pkg in LEVEL1_PACKAGES:
        current = current_counts.get(pkg, 0)
        if baseline:
            pkg_data = baseline.get("packages", {}).get(pkg, {})
            prev = pkg_data.get("error_count", 0) if pkg_data else 0
            diff = current - prev
            if diff < 0:
                diff_str = f"{Colors.GREEN}▼{abs(diff)}{Colors.RESET}"
            elif diff > 0:
                diff_str = f"{Colors.RED}▲{diff}{Colors.RESET}"
            else:
                diff_str = "="
            status = f"{current:3d} errors {diff_str}"
        else:
            status = f"{current:3d} errors"

        if current == 0:
            print(f"  {Colors.GREEN}✅ {pkg:15}{Colors.RESET} {status}")
        else:
            print(f"  {Colors.YELLOW}⚠️  {pkg:15}{Colors.RESET} {status}")

    print_section("📈 Overall Progress")
    print(f"  {Colors.BOLD}Total Errors:{Colors.RESET} {total_current}")
    print(f"  {Colors.BOLD}Timestamp:{Colors.RESET} {datetime.now().isoformat()}")

    if baseline:
        baseline_total = baseline.get("total_errors", 0)
        if baseline_total > 0:
            fixed = baseline_total - total_current
            print(f"\n  {Colors.BOLD}Since Baseline:{Colors.RESET}")
            print(f"  Initial:  {baseline_total}")
            print(f"  Current:  {total_current}")
            print(f"  Fixed:    {fixed}")
            print(f"\n  Progress: {print_progress_bar(total_current, baseline_total)}")

    # Summary
    print_section("📋 Summary")
    level2_errors = sum(current_counts.get(pkg, 0) for pkg in LEVEL2_PACKAGES)
    level1_errors = sum(current_counts.get(pkg, 0) for pkg in LEVEL1_PACKAGES)

    if level2_errors == 0:
        print(f"  {Colors.GREEN}✅ Level 2 (Strict): All packages pass!{Colors.RESET}")
    else:
        print(f"  {Colors.RED}❌ Level 2 (Strict): {level2_errors} errors remaining{Colors.RESET}")

    if level1_errors == 0:
        print(f"  {Colors.GREEN}✅ Level 1: All packages pass!{Colors.RESET}")
    else:
        print(f"  {Colors.YELLOW}⚠️  Level 1: {level1_errors} errors remaining{Colors.RESET}")

    print()
    return 0 if total_current == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
