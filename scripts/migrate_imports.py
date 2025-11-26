#!/usr/bin/env python3
"""Auto-migrate deprecated imports to new paths."""

import argparse
import re
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


def migrate_file(filepath: Path, fix: bool = False) -> list[str]:
    """Migrate imports in a single file."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    changes = []
    new_content = content

    for old_pattern, new_import in IMPORT_MAPPINGS.items():
        if re.search(old_pattern, content):
            changes.append(f"{filepath}: {old_pattern} → {new_import}")
            if fix:
                new_content = re.sub(old_pattern, new_import, new_content)

    if fix and changes:
        filepath.write_text(new_content, encoding="utf-8")

    return changes


def main():
    parser = argparse.ArgumentParser(description="Migrate deprecated imports")
    parser.add_argument("--check", action="store_true", help="Dry run, show changes")
    parser.add_argument("--fix", action="store_true", help="Apply changes")
    parser.add_argument("path", nargs="?", default=".", help="Path to scan")
    args = parser.parse_args()

    if not args.check and not args.fix:
        args.check = True

    path = Path(args.path)
    files = [path] if path.is_file() else list(path.rglob("*.py"))

    all_changes = []
    for filepath in files:
        if "__pycache__" in str(filepath):
            continue
        changes = migrate_file(filepath, fix=args.fix)
        all_changes.extend(changes)

    if all_changes:
        print(f"Found {len(all_changes)} deprecated imports:")
        for change in all_changes:
            print(f"  {change}")
        if args.fix:
            print(f"\n✅ Fixed {len(all_changes)} imports")
    else:
        print("✅ No deprecated imports found")


if __name__ == "__main__":
    main()
