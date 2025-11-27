#!/usr/bin/env python3
"""Analyze deprecation usage statistics and generate reports."""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class UsageStats(TypedDict):
    """Statistics about deprecated import usage."""

    total_calls: int
    unique_callers: int
    by_module: dict[str, int]
    files_with_deprecations: list[str]


DEPRECATED_IMPORT_PATTERNS = [
    r"from src\.utils import",
    r"from src\.logging_setup import",
    r"from src\.constants import",
    r"from src\.exceptions import",
    r"from src\.models import",
    r"from src\.budget_tracker import",
    r"from src\.neo4j_utils import",
    r"from src\.health_check import",
    r"from src\.worker import",
    r"from src\.gemini_model_client import",
    r"from src\.data_loader import",
    r"from src\.semantic_analysis import",
    r"from src\.qa_rag_system import",
    r"from src\.caching_layer import",
    r"from src\.smart_autocomplete import",
    r"from src\.graph_enhanced_router import",
    r"import src\.utils",
    r"import src\.constants",
    r"import src\.models",
]


def analyze_file(filepath: Path) -> dict[str, int]:
    """Analyze a single file for deprecated imports.

    Returns a dict mapping deprecated module names to their occurrence count.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return {}

    module_counts: dict[str, int] = defaultdict(int)

    for pattern in DEPRECATED_IMPORT_PATTERNS:
        # Use finditer to count all matches
        matches = list(re.finditer(pattern, content))
        if matches:
            # Extract module name from pattern - handle escaped dots
            # The pattern contains \. which represents a literal dot
            module_match = re.search(r"src\\\.\(?(\\w\+|\w+)", pattern)
            if module_match:
                replacement = "\\w+"
                group_value = module_match.group(1).replace(replacement, "")
                module_name = f"src.{group_value}"
                if not module_name.endswith("."):
                    module_counts[module_name] += len(matches)
            else:
                # Fallback: extract module name by parsing the pattern string
                # Pattern looks like: r"from src\.utils import" or r"import src\.models"
                pattern_clean = pattern.replace(r"\.", ".")
                module_match2 = re.search(r"src\.(\w+)", pattern_clean)
                if module_match2:
                    module_name = f"src.{module_match2.group(1)}"
                    module_counts[module_name] += len(matches)

    return dict(module_counts)


def analyze_usage(path: Path, exclude_patterns: list[str] | None = None) -> UsageStats:
    """Analyze deprecated import usage in a directory.

    Args:
        path: Directory or file to analyze
        exclude_patterns: List of glob patterns to exclude

    Returns:
        UsageStats with analysis results
    """
    if exclude_patterns is None:
        exclude_patterns = []

    files = [path] if path.is_file() else list(path.rglob("*.py"))

    total_calls = 0
    by_module: dict[str, int] = defaultdict(int)
    files_with_deprecations: list[str] = []

    for filepath in files:
        # Skip excluded patterns
        filepath_str = str(filepath)
        if any(pattern in filepath_str for pattern in exclude_patterns):
            continue
        if "__pycache__" in filepath_str:
            continue

        file_stats = analyze_file(filepath)
        if file_stats:
            files_with_deprecations.append(str(filepath))
            for module, count in file_stats.items():
                total_calls += count
                by_module[module] += count

    return UsageStats(
        total_calls=total_calls,
        unique_callers=len(files_with_deprecations),
        by_module=dict(by_module),
        files_with_deprecations=files_with_deprecations,
    )


def get_trend_indicator(current: int, previous: int) -> str:
    """Get a trend indicator based on comparing current vs previous values."""
    if previous == 0:
        return "NEW" if current > 0 else "STABLE"
    if current < previous:
        return "DECREASING ✅"
    elif current > previous:
        return "INCREASING ⚠️"
    else:
        return "STABLE"


def generate_summary_text(stats: UsageStats) -> str:
    """Generate a text summary of deprecation usage."""
    lines = [
        "📊 Deprecation Usage Summary",
        "═" * 42,
        f"Total deprecated calls: {stats['total_calls']}",
        f"Unique callers: {stats['unique_callers']}",
    ]

    if stats["by_module"]:
        # Sort by count descending and take top 10
        sorted_modules = sorted(
            stats["by_module"].items(), key=lambda x: x[1], reverse=True
        )[:10]

        lines.append("")
        lines.append("Top modules:")
        for module, count in sorted_modules:
            lines.append(f"  {module}: {count} call(s)")

    lines.append("═" * 42)
    return "\n".join(lines)


def generate_report(
    stats: UsageStats, output_path: Path | None = None, title: str = "Deprecation Report"
) -> str:
    """Generate an HTML report from usage statistics.

    Args:
        stats: Usage statistics from analyze_usage
        output_path: Optional path to write the HTML file
        title: Title for the report

    Returns:
        HTML content as string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort modules by count
    sorted_modules = sorted(
        stats["by_module"].items(), key=lambda x: x[1], reverse=True
    )

    # Generate module rows
    module_rows = ""
    for module, count in sorted_modules:
        module_rows += f"""
        <tr>
            <td>{module}</td>
            <td>{count}</td>
        </tr>"""

    # Generate file list
    file_list = ""
    for filepath in sorted(stats["files_with_deprecations"]):
        file_list += f"<li><code>{filepath}</code></li>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .stat-label {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
        }}
        .file-list {{
            max-height: 300px;
            overflow-y: auto;
            background: #f8f9fa;
            padding: 10px 20px;
            border-radius: 4px;
        }}
        .file-list li {{
            margin: 4px 0;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
            text-align: right;
        }}
        code {{
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {title}</h1>

        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{stats['total_calls']}</div>
                <div class="stat-label">Total Deprecated Calls</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats['unique_callers']}</div>
                <div class="stat-label">Files with Deprecations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(stats['by_module'])}</div>
                <div class="stat-label">Deprecated Modules Used</div>
            </div>
        </div>

        <h2>Usage by Module</h2>
        <table>
            <thead>
                <tr>
                    <th>Module</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
                {module_rows}
            </tbody>
        </table>

        <h2>Affected Files</h2>
        <ul class="file-list">
            {file_list}
        </ul>

        <p class="timestamp">Generated: {timestamp}</p>
    </div>
</body>
</html>
"""

    if output_path:
        output_path.write_text(html, encoding="utf-8")

    return html


def save_stats_json(stats: UsageStats, output_path: Path) -> None:
    """Save statistics to a JSON file for trend analysis."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main(args: list[str] | None = None) -> int:
    """Main entry point for the deprecation stats tool."""
    parser = argparse.ArgumentParser(
        description="Analyze deprecated import usage and generate reports"
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to scan (file or directory, default: current directory)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Exclude paths containing pattern (can be used multiple times)",
    )
    parser.add_argument(
        "--html",
        metavar="FILE",
        help="Generate HTML report to specified file",
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="Save statistics to JSON file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress text summary output",
    )

    parsed_args = parser.parse_args(args)

    path = Path(parsed_args.path)
    if not path.exists():
        print(f"Error: Path '{path}' does not exist", file=sys.stderr)
        return 1

    stats = analyze_usage(path, parsed_args.exclude)

    # Output summary unless quiet
    if not parsed_args.quiet:
        print(generate_summary_text(stats))

    # Generate HTML report if requested
    if parsed_args.html:
        html_path = Path(parsed_args.html)
        generate_report(stats, html_path)
        print(f"\n✅ HTML report saved to: {html_path}")

    # Save JSON stats if requested
    if parsed_args.json:
        json_path = Path(parsed_args.json)
        save_stats_json(stats, json_path)
        print(f"✅ Stats saved to: {json_path}")

    # Set environment variable for CI usage
    os.environ["TOTAL_CALLS"] = str(stats["total_calls"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
