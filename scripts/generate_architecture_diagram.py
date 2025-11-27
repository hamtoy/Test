#!/usr/bin/env python3
"""
v3.0 Architecture Diagram Generator.

Automatically generates a Mermaid diagram of the package structure
and updates docs/ARCHITECTURE.md.

Usage:
    python scripts/generate_architecture_diagram.py [--output FILE]

Exit Codes:
    0: Diagram generated successfully
    1: Error occurred
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

# Known package dependencies (core architectural relationships)
PACKAGE_DEPENDENCIES: Dict[str, List[str]] = {
    "agent": ["config", "core", "caching", "infra"],
    "qa": ["llm", "core", "caching", "infra"],
    "workflow": ["agent", "processing", "core"],
    "llm": ["config", "core"],
    "processing": ["config", "core"],
    "caching": ["config"],
    "routing": ["core", "config"],
    "features": ["config", "core"],
    "analysis": ["core"],
    "infra": ["config"],
    "graph": ["config"],
    "ui": ["config"],
}


def scan_package_structure() -> Dict[str, List[str]]:
    """Scan src/ package structure and return module information.

    Returns:
        Dictionary mapping package names to list of module names
    """
    structure: Dict[str, List[str]] = {}
    src_path = Path("src")

    if not src_path.exists():
        return structure

    for package_dir in src_path.iterdir():
        if not package_dir.is_dir():
            continue
        if package_dir.name.startswith("_"):
            continue
        if package_dir.name.startswith("."):
            continue

        modules = [
            f.stem
            for f in package_dir.glob("*.py")
            if f.stem != "__init__" and not f.stem.startswith("_")
        ]

        if modules:  # Only include packages with modules
            structure[package_dir.name] = sorted(modules)

    return structure


def analyze_imports(package_dir: Path) -> Set[str]:
    """Analyze imports in a package to detect dependencies.

    Args:
        package_dir: Path to the package directory

    Returns:
        Set of package names that are imported
    """
    imports: Set[str] = set()

    for py_file in package_dir.glob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if len(parts) >= 2 and parts[0] == "src":
                        imports.add(parts[1])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 2 and parts[0] == "src":
                        imports.add(parts[1])

    return imports


def generate_mermaid_diagram(structure: Dict[str, List[str]]) -> str:
    """Generate Mermaid diagram from package structure.

    Args:
        structure: Dictionary of package names to module lists

    Returns:
        Mermaid diagram as string
    """
    lines = [
        "```mermaid",
        "graph TD",
        "    %% v3.0 Package Architecture",
        "    Main[src/main.py] --> Agent[agent/]",
        "    Main --> CLI[cli.py]",
        "    Main --> QA[qa/]",
        "",
        "    %% Core Dependencies",
    ]

    # Add package dependencies
    added_deps: Set[str] = set()
    for pkg, deps in PACKAGE_DEPENDENCIES.items():
        if pkg in structure:
            for dep in deps:
                if dep in structure:
                    dep_key = f"{pkg}->{dep}"
                    if dep_key not in added_deps:
                        pkg_name = pkg.capitalize()
                        dep_name = dep.capitalize()
                        lines.append(f"    {pkg_name}[{pkg}/] --> {dep_name}[{dep}/]")
                        added_deps.add(dep_key)

    # Add subgraph for core packages
    lines.extend(
        [
            "",
            "    %% v3.0 Public API",
            "    subgraph PublicAPI[\"v3.0 Public API\"]",
            "        Agent",
            "        Config[config/]",
            "        Core[core/]",
            "    end",
            "",
            "    %% External Services",
            "    Agent --> Gemini[Gemini API]",
            "    QA --> Neo4j[(Neo4j Graph)]",
            "```",
        ]
    )

    return "\n".join(lines)


def generate_module_tree(structure: Dict[str, List[str]]) -> str:
    """Generate a text-based module tree.

    Args:
        structure: Dictionary of package names to module lists

    Returns:
        Module tree as formatted string
    """
    lines = ["```", "src/"]

    sorted_packages = sorted(structure.keys())
    for i, pkg in enumerate(sorted_packages):
        is_last_pkg = i == len(sorted_packages) - 1
        prefix = "└── " if is_last_pkg else "├── "
        lines.append(f"{prefix}{pkg}/")

        modules = structure[pkg]
        for j, mod in enumerate(modules):
            is_last_mod = j == len(modules) - 1
            mod_prefix = "    └── " if is_last_mod else "    ├── "
            if is_last_pkg:
                mod_prefix = "    " + ("└── " if is_last_mod else "├── ")
            lines.append(f"{mod_prefix}{mod}.py")

    lines.append("```")
    return "\n".join(lines)


def update_architecture_md(diagram: str, tree: str) -> bool:
    """Update docs/ARCHITECTURE.md with generated diagram.

    Args:
        diagram: Mermaid diagram string
        tree: Module tree string

    Returns:
        True if file was updated, False otherwise
    """
    arch_path = Path("docs/ARCHITECTURE.md")

    if not arch_path.exists():
        print(f"Warning: {arch_path} does not exist")
        return False

    content = arch_path.read_text(encoding="utf-8")

    # Look for auto-generated section markers
    start_marker = "<!-- AUTO-GENERATED: v3.0 Package Structure -->"
    end_marker = "<!-- END AUTO-GENERATED -->"

    new_section = f"""{start_marker}

## v3.0 Package Architecture

{diagram}

### Module Tree

{tree}

{end_marker}"""

    if start_marker in content and end_marker in content:
        # Replace existing auto-generated section
        pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
        content = re.sub(pattern, new_section, content, flags=re.DOTALL)
    else:
        # Append at the end if markers don't exist
        content = content.rstrip() + "\n\n" + new_section + "\n"

    arch_path.write_text(content, encoding="utf-8")
    return True


def main(args: list[str] | None = None) -> int:
    """Main entry point for the architecture diagram generator.

    Args:
        args: Command line arguments (for testing)

    Returns:
        0 on success, 1 on error
    """
    parser = argparse.ArgumentParser(
        description="Generate v3.0 architecture diagram (Mermaid)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: update docs/ARCHITECTURE.md)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Only print diagram, don't update files",
    )

    parsed_args = parser.parse_args(args)

    print("🏗️  v3.0 Architecture Diagram Generator")
    print("=" * 50)

    # Scan package structure
    structure = scan_package_structure()

    if not structure:
        print("❌ No packages found in src/")
        return 1

    print(f"Found {len(structure)} packages:")
    for pkg, modules in sorted(structure.items()):
        print(f"  📦 {pkg}: {len(modules)} modules")

    # Generate diagrams
    diagram = generate_mermaid_diagram(structure)
    tree = generate_module_tree(structure)

    print()

    if parsed_args.print_only:
        print("=== Mermaid Diagram ===")
        print(diagram)
        print()
        print("=== Module Tree ===")
        print(tree)
        return 0

    if parsed_args.output:
        output_content = f"# v3.0 Package Architecture\n\n{diagram}\n\n## Module Tree\n\n{tree}\n"
        parsed_args.output.write_text(output_content, encoding="utf-8")
        print(f"✅ Diagram written to {parsed_args.output}")
    else:
        if update_architecture_md(diagram, tree):
            print("✅ docs/ARCHITECTURE.md updated with v3.0 diagram")
        else:
            print("⚠️  Could not update docs/ARCHITECTURE.md")
            print("  Printing diagram instead:")
            print()
            print(diagram)

    return 0


if __name__ == "__main__":
    sys.exit(main())
