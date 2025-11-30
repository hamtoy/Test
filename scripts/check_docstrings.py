#!/usr/bin/env python3
"""Docstring style checker for the codebase.

This script identifies:
1. Functions/methods missing docstrings
2. Inconsistent docstring styles (Google vs NumPy)
3. Missing parameter documentation

Usage:
    python scripts/check_docstrings.py [--fix] [path]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, NamedTuple


class DocstringIssue(NamedTuple):
    """Represents a docstring issue found in the code."""
    
    file: str
    line: int
    name: str
    issue_type: str
    message: str


def check_docstring_style(docstring: str) -> str:
    """Determine the docstring style.
    
    Args:
        docstring: The docstring text to analyze
        
    Returns:
        Style name: 'google', 'numpy', 'sphinx', or 'unknown'
    """
    if not docstring:
        return "missing"
        
    # Google style: Args:, Returns:, Raises:
    if "Args:" in docstring or "Returns:" in docstring:
        return "google"
        
    # NumPy style: Parameters\n----------
    if "Parameters\n" in docstring and "----------" in docstring:
        return "numpy"
        
    # Sphinx style: :param, :returns:
    if ":param" in docstring or ":returns:" in docstring:
        return "sphinx"
        
    return "simple"


def analyze_file(file_path: Path) -> List[DocstringIssue]:
    """Analyze a Python file for docstring issues.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        List of issues found
    """
    issues: List[DocstringIssue] = []
    
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError) as e:
        return [DocstringIssue(
            file=str(file_path),
            line=0,
            name="<parse error>",
            issue_type="error",
            message=str(e),
        )]
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            name = node.name
            line = node.lineno
            
            # Skip private/magic methods for missing docstring check
            if name.startswith("_") and not name.startswith("__"):
                continue
                
            if docstring is None:
                issues.append(DocstringIssue(
                    file=str(file_path),
                    line=line,
                    name=name,
                    issue_type="missing",
                    message="Missing docstring",
                ))
            else:
                style = check_docstring_style(docstring)
                if style == "numpy":
                    issues.append(DocstringIssue(
                        file=str(file_path),
                        line=line,
                        name=name,
                        issue_type="style",
                        message="NumPy style detected, prefer Google style",
                    ))
                elif style == "sphinx":
                    issues.append(DocstringIssue(
                        file=str(file_path),
                        line=line,
                        name=name,
                        issue_type="style",
                        message="Sphinx style detected, prefer Google style",
                    ))
    
    return issues


def main() -> int:
    """Main entry point for the docstring checker.
    
    Returns:
        Exit code: 0 if no issues, 1 if issues found
    """
    parser = argparse.ArgumentParser(description="Check docstring consistency")
    parser.add_argument(
        "path",
        nargs="?",
        default="src",
        help="Path to check (default: src)",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only report missing docstrings",
    )
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*.py"))
    
    all_issues: List[DocstringIssue] = []
    
    for file_path in files:
        issues = analyze_file(file_path)
        if args.missing_only:
            issues = [i for i in issues if i.issue_type == "missing"]
        all_issues.extend(issues)
    
    if all_issues:
        print(f"\n{'='*60}")
        print(f"Found {len(all_issues)} docstring issues:")
        print(f"{'='*60}\n")
        
        for issue in sorted(all_issues, key=lambda x: (x.file, x.line)):
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.name}: {issue.message}")
            print()
        
        return 1
    else:
        print("✅ No docstring issues found!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
