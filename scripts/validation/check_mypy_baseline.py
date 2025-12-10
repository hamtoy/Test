#!/usr/bin/env python3
"""Mypy Baseline Measurement Tool.

Measures the current state of mypy errors across the project and generates
a baseline report for tracking progress during type annotation migration.

Usage:
    python scripts/check_mypy_baseline.py [--output report.json] [--html]

This tool:
1. Runs mypy on the entire src/ directory
2. Categorizes errors by package and error type
3. Generates a JSON report and optionally an HTML report
4. Tracks progress over time when run repeatedly
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import LEVEL1_PACKAGES, LEVEL2_PACKAGES


@dataclass
class PackageReport:
    """Report for a single package."""

    name: str
    error_count: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    files_with_errors: list[str] = field(default_factory=list)


@dataclass
class BaselineReport:
    """Complete baseline report."""

    timestamp: str
    total_errors: int = 0
    total_files: int = 0
    packages: dict[str, PackageReport] = field(default_factory=dict)
    level1_packages: list[str] = field(default_factory=list)
    level2_packages: list[str] = field(default_factory=list)


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

        # Parse format: path:line:col: error: message [error-code]
        parts = line.split(": error:", 1)
        if len(parts) != 2:
            continue

        location = parts[0]
        message_part = parts[1].strip()

        # Extract error code if present
        error_code = "unknown"
        if "[" in message_part and message_part.endswith("]"):
            code_start = message_part.rfind("[")
            error_code = message_part[code_start + 1 : -1]
            message = message_part[:code_start].strip()
        else:
            message = message_part

        # Parse location
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

    # Find 'src' in path and get the next part
    if "src" in parts:
        src_idx = parts.index("src")
        if src_idx + 1 < len(parts):
            return parts[src_idx + 1]

    return "root"


def create_baseline_report(errors: dict[str, list[dict[str, Any]]]) -> BaselineReport:
    """Create a baseline report from parsed errors.

    Args:
        errors: Dictionary of errors by file path

    Returns:
        Complete baseline report
    """
    report = BaselineReport(
        timestamp=datetime.now().isoformat(),
        level1_packages=list(LEVEL1_PACKAGES),
        level2_packages=list(LEVEL2_PACKAGES),
    )

    package_reports: dict[str, PackageReport] = {}

    for file_path, file_errors in errors.items():
        pkg_name = get_package_name(file_path)

        if pkg_name not in package_reports:
            package_reports[pkg_name] = PackageReport(name=pkg_name)

        pkg_report = package_reports[pkg_name]
        pkg_report.error_count += len(file_errors)
        pkg_report.files_with_errors.append(file_path)

        for error in file_errors:
            error_code = error["code"]
            pkg_report.errors_by_type[error_code] = (
                pkg_report.errors_by_type.get(error_code, 0) + 1
            )

    report.packages = package_reports
    report.total_errors = sum(p.error_count for p in package_reports.values())
    report.total_files = len(errors)

    return report


def report_to_dict(report: BaselineReport) -> dict[str, Any]:
    """Convert baseline report to dictionary for JSON serialization.

    Args:
        report: BaselineReport instance

    Returns:
        Dictionary representation
    """
    return {
        "timestamp": report.timestamp,
        "total_errors": report.total_errors,
        "total_files": report.total_files,
        "level1_packages": report.level1_packages,
        "level2_packages": report.level2_packages,
        "packages": {
            name: {
                "name": pkg.name,
                "error_count": pkg.error_count,
                "errors_by_type": pkg.errors_by_type,
                "files_with_errors": pkg.files_with_errors,
            }
            for name, pkg in report.packages.items()
        },
    }


def generate_html_report(report: BaselineReport, output_path: Path) -> None:
    """Generate an HTML report from the baseline report.

    Args:
        report: BaselineReport instance
        output_path: Path to write the HTML file
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mypy Baseline Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; }}
        .package {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
        .package h3 {{ margin-top: 0; }}
        .level2 {{ border-color: #4CAF50; }}
        .level1 {{ border-color: #2196F3; }}
        .error-count {{ font-size: 2rem; font-weight: bold; color: #f44336; }}
        .success {{ color: #4CAF50; }}
        .error-types {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }}
        .error-type {{ background: #ffebee; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.875rem; }}
    </style>
</head>
<body>
    <h1>📊 Mypy Baseline Report</h1>
    <div class="summary">
        <p><strong>Generated:</strong> {report.timestamp}</p>
        <p><strong>Total Errors:</strong> <span class="error-count {"success" if report.total_errors == 0 else ""}">{report.total_errors}</span></p>
        <p><strong>Files with Errors:</strong> {report.total_files}</p>
    </div>

    <h2>📦 Level 2 Packages (Strict Mode)</h2>
"""

    for pkg_name in report.level2_packages:
        pkg = report.packages.get(pkg_name)
        if pkg:
            html += f"""
    <div class="package level2">
        <h3>{pkg.name}</h3>
        <p>Errors: <strong>{pkg.error_count}</strong></p>
        <div class="error-types">
            {"".join(f'<span class="error-type">{code}: {count}</span>' for code, count in pkg.errors_by_type.items())}
        </div>
    </div>
"""
        else:
            html += f"""
    <div class="package level2">
        <h3>{pkg_name}</h3>
        <p>Errors: <strong class="success">0</strong> ✅</p>
    </div>
"""

    html += """
    <h2>📦 Level 1 Packages</h2>
"""

    for pkg_name in report.level1_packages:
        pkg = report.packages.get(pkg_name)
        if pkg:
            html += f"""
    <div class="package level1">
        <h3>{pkg.name}</h3>
        <p>Errors: <strong>{pkg.error_count}</strong></p>
        <div class="error-types">
            {"".join(f'<span class="error-type">{code}: {count}</span>' for code, count in pkg.errors_by_type.items())}
        </div>
    </div>
"""
        else:
            html += f"""
    <div class="package level1">
        <h3>{pkg_name}</h3>
        <p>Errors: <strong class="success">0</strong> ✅</p>
    </div>
"""

    html += """
</body>
</html>
"""

    output_path.write_text(html)


def print_summary(report: BaselineReport) -> None:
    """Print a summary of the baseline report to stdout.

    Args:
        report: BaselineReport instance
    """
    print("\n" + "=" * 60)
    print("📊 MYPY BASELINE REPORT")
    print("=" * 60)
    print(f"\n🕐 Generated: {report.timestamp}")
    print(f"📈 Total Errors: {report.total_errors}")
    print(f"📁 Files with Errors: {report.total_files}")

    print("\n" + "-" * 40)
    print("📦 Level 2 Packages (Strict Mode)")
    print("-" * 40)
    for pkg_name in report.level2_packages:
        pkg = report.packages.get(pkg_name)
        status = f"❌ {pkg.error_count} errors" if pkg else "✅ 0 errors"
        print(f"  {pkg_name:15} {status}")

    print("\n" + "-" * 40)
    print("📦 Level 1 Packages")
    print("-" * 40)
    for pkg_name in report.level1_packages:
        pkg = report.packages.get(pkg_name)
        status = f"❌ {pkg.error_count} errors" if pkg else "✅ 0 errors"
        print(f"  {pkg_name:15} {status}")

    print("\n" + "=" * 60)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Measure mypy baseline and generate reports"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("mypy_baseline.json"),
        help="Output JSON file path (default: mypy_baseline.json)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report in addition to JSON",
    )
    parser.add_argument(
        "--target",
        "-t",
        type=str,
        default="src/",
        help="Target directory to analyze (default: src/)",
    )
    args = parser.parse_args()

    print("🔍 Running mypy baseline check...")
    return_code, output = run_mypy(args.target)

    errors = parse_mypy_output(output)
    report = create_baseline_report(errors)

    # Save JSON report
    report_dict = report_to_dict(report)
    args.output.write_text(json.dumps(report_dict, indent=2))
    print(f"📄 JSON report saved to: {args.output}")

    # Generate HTML if requested
    if args.html:
        html_path = args.output.with_suffix(".html")
        generate_html_report(report, html_path)
        print(f"🌐 HTML report saved to: {html_path}")

    print_summary(report)

    return 0 if report.total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
