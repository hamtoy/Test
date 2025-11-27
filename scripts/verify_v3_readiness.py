#!/usr/bin/env python3
"""v3.0 Readiness Verification Script.

Checks the codebase for v3.0 compatibility:
- Deprecated imports
- Shim file usage
- Version requirements
- Public API availability

This script scans the entire codebase to detect deprecated shim imports
and generates a readiness report for v3.0 migration.

Usage:
    python scripts/verify_v3_readiness.py [--strict]

Exit Codes:
    0: Ready for v3.0
    1: Issues found
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple


class Issue(NamedTuple):
    """Represents a v3.0 readiness issue."""

    filepath: Path
    line_number: int
    issue_type: str
    message: str
    severity: str  # "error", "warning", "info"


# Deprecated import patterns for v3.0
DEPRECATED_IMPORTS: Dict[str, str] = {
    r"from\s+src\.utils\s+import": "Use: from src.infra.utils import",
    r"from\s+src\.logging_setup\s+import": "Use: from src.infra.logging import",
    r"from\s+src\.constants\s+import": "Use: from src.config.constants import",
    r"from\s+src\.exceptions\s+import": "Use: from src.config.exceptions import",
    r"from\s+src\.models\s+import": "Use: from src.core.models import",
    r"from\s+src\.neo4j_utils\s+import": "Use: from src.infra.neo4j import",
    r"from\s+src\.worker\s+import": "Use: from src.infra.worker import",
    r"from\s+src\.data_loader\s+import": "Use: from src.processing.loader import",
    r"from\s+src\.qa_rag_system\s+import": "Use: from src.qa.rag_system import",
    r"from\s+src\.caching_layer\s+import": "Use: from src.caching.layer import",
    r"from\s+src\.graph_enhanced_router\s+import": "Use: from src.routing.graph_router import",
    r"from\s+src\.budget_tracker\s+import": "Use: from src.infra.budget import",
    r"from\s+src\.health_check\s+import": "Use: from src.infra.health import",
    r"from\s+src\.gemini_model_client\s+import": "Use: from src.llm.gemini import",
    r"from\s+src\.semantic_analysis\s+import": "Use: from src.analysis.semantic import",
    r"from\s+src\.smart_autocomplete\s+import": "Use: from src.features.autocomplete import",
}

# Files that are shims and should eventually be removed
SHIM_FILES: List[str] = [
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
    "src/budget_tracker.py",
    "src/health_check.py",
    "src/gemini_model_client.py",
    "src/semantic_analysis.py",
    "src/smart_autocomplete.py",
    "src/config.py",  # shim for src.config package
    "src/adaptive_difficulty.py",
    "src/advanced_context_augmentation.py",
    "src/cache_analytics.py",
    "src/dynamic_template_generator.py",
    "src/graph_schema_builder.py",
    "src/integrated_qa_pipeline.py",
    "src/lats_searcher.py",
    "src/list_models.py",
    "src/memory_augmented_qa.py",
    "src/multi_agent_qa_system.py",
    "src/multimodal_understanding.py",
    "src/qa_generator.py",
    "src/qa_system_factory.py",
    "src/real_time_constraint_enforcer.py",
    "src/self_correcting_chain.py",
]

# Files to exclude from checking
EXCLUDE_PATHS: List[str] = [
    "tests/test_deprecation_warnings.py",
    "tests/test_enhanced_deprecation.py",
    "tests/test_migrate_imports.py",  # Tests migration functionality
    "tests/test_deprecation_stats.py",  # Tests deprecation stats
    "scripts/migrate_imports.py",
    "scripts/check_deprecated_imports.py",
    "scripts/verify_v3_readiness.py",
]


def check_file_for_deprecated_imports(filepath: Path) -> List[Issue]:
    """Check a file for deprecated import patterns.

    Args:
        filepath: Path to the Python file

    Returns:
        List of issues found
    """
    issues: List[Issue] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return issues

    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, replacement in DEPRECATED_IMPORTS.items():
            if re.search(pattern, line):
                issues.append(
                    Issue(
                        filepath=filepath,
                        line_number=line_num,
                        issue_type="deprecated_import",
                        message=f"Deprecated import detected. {replacement}",
                        severity="error",
                    )
                )

    return issues


def check_shim_files() -> List[Issue]:
    """Check for existence of shim files.

    Returns:
        List of issues for existing shim files
    """
    issues: List[Issue] = []

    for shim_file in SHIM_FILES:
        path = Path(shim_file)
        if path.exists():
            issues.append(
                Issue(
                    filepath=path,
                    line_number=0,
                    issue_type="shim_file",
                    message="Shim file exists (should be removed in v3.0 or later)",
                    severity="warning",
                )
            )

    return issues


def check_version_requirements() -> List[Issue]:
    """Check Python version requirements in configuration files.

    Returns:
        List of version-related issues
    """
    issues: List[Issue] = []

    # Check pyproject.toml
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")

        # Check for Python version constraint
        if 'requires-python = ">=3.10' not in content:
            issues.append(
                Issue(
                    filepath=pyproject,
                    line_number=0,
                    issue_type="version_requirement",
                    message="Python version should be >=3.10 for v3.0",
                    severity="info",
                )
            )

    return issues


def check_public_api() -> List[Issue]:
    """Check that v3.0 public API is properly defined.

    Returns:
        List of API-related issues
    """
    issues: List[Issue] = []

    init_file = Path("src/__init__.py")
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")

        # Check for version
        if '__version__ = "3.0.0"' not in content:
            issues.append(
                Issue(
                    filepath=init_file,
                    line_number=0,
                    issue_type="version",
                    message='Missing or incorrect version. Expected: __version__ = "3.0.0"',
                    severity="info",
                )
            )

        # Check for public API exports
        required_exports = [
            "GeminiAgent",
            "AppConfig",
            "WorkflowResult",
            "EvaluationResultSchema",
            "QueryResult",
        ]

        for export in required_exports:
            if f'"{export}"' not in content and f"'{export}'" not in content:
                issues.append(
                    Issue(
                        filepath=init_file,
                        line_number=0,
                        issue_type="public_api",
                        message=f"Missing public API export: {export}",
                        severity="warning",
                    )
                )

    return issues


def collect_python_files(exclude_patterns: List[str] | None = None) -> List[Path]:
    """Collect all Python files to check.

    Args:
        exclude_patterns: List of path patterns to exclude

    Returns:
        List of Python file paths
    """
    if exclude_patterns is None:
        exclude_patterns = EXCLUDE_PATHS

    files: List[Path] = []

    for py_file in Path(".").rglob("*.py"):
        # Skip common exclusions
        if "__pycache__" in str(py_file):
            continue
        if ".venv" in str(py_file):
            continue
        if "notion-neo4j-graph" in str(py_file):
            continue

        # Check exclusion patterns
        path_str = str(py_file).replace("\\", "/")
        if any(path_str.endswith(exc) for exc in exclude_patterns):
            continue

        # Skip shim files themselves
        if path_str in SHIM_FILES:
            continue

        files.append(py_file)

    return files


def run_verification(
    strict: bool = False,
) -> Tuple[List[Issue], Dict[str, int]]:
    """Run all v3.0 readiness checks.

    Args:
        strict: If True, treat all issues as errors

    Returns:
        Tuple of (all_issues, summary_counts)
    """
    all_issues: List[Issue] = []

    # 1. Check for deprecated imports
    files = collect_python_files()
    for filepath in files:
        issues = check_file_for_deprecated_imports(filepath)
        all_issues.extend(issues)

    # 2. Check for shim files
    all_issues.extend(check_shim_files())

    # 3. Check version requirements
    all_issues.extend(check_version_requirements())

    # 4. Check public API
    all_issues.extend(check_public_api())

    # Count by severity
    summary: Dict[str, int] = {
        "error": sum(1 for i in all_issues if i.severity == "error"),
        "warning": sum(1 for i in all_issues if i.severity == "warning"),
        "info": sum(1 for i in all_issues if i.severity == "info"),
    }

    return all_issues, summary


def main(args: list[str] | None = None) -> int:
    """Main entry point for the v3.0 readiness verification.

    Args:
        args: Command line arguments

    Returns:
        0 if ready for v3.0, 1 if issues found
    """
    parser = argparse.ArgumentParser(description="Verify v3.0 readiness")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any issue (including warnings)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    parsed_args = parser.parse_args(args)

    print("🔍 v3.0 Readiness Verification")
    print("=" * 60)

    issues, summary = run_verification(strict=parsed_args.strict)

    # Group issues by type
    by_type: Dict[str, List[Issue]] = {}
    for issue in issues:
        if issue.issue_type not in by_type:
            by_type[issue.issue_type] = []
        by_type[issue.issue_type].append(issue)

    # Print issues by type
    if issues:
        for issue_type, type_issues in by_type.items():
            print(f"\n📋 {issue_type.replace('_', ' ').title()} ({len(type_issues)}):")
            for issue in type_issues:
                severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                    issue.severity, "•"
                )
                if issue.line_number > 0:
                    print(f"  {severity_icon} {issue.filepath}:{issue.line_number}")
                else:
                    print(f"  {severity_icon} {issue.filepath}")
                print(f"      {issue.message}")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  Errors:   {summary['error']}")
    print(f"  Warnings: {summary['warning']}")
    print(f"  Info:     {summary['info']}")

    # Determine exit code
    if parsed_args.strict:
        has_failures = summary["error"] > 0 or summary["warning"] > 0
    else:
        has_failures = summary["error"] > 0

    if has_failures:
        print("\n❌ v3.0 readiness check FAILED")
        print("\nTo fix deprecated imports, run:")
        print("  migrate-imports --fix")
        return 1
    else:
        print("\n✅ v3.0 readiness check PASSED")
        if summary["warning"] > 0:
            print(f"   (with {summary['warning']} warning(s) to address)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
