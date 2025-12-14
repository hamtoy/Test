"""Docstring verification script.

Extracts module docstrings and checks if they match the actual code content.
"""

import ast
from pathlib import Path


def get_module_docstring(filepath: Path) -> tuple[str, list[str]]:
    """Extract module docstring and top-level class/function names."""
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Get module docstring
        docstring = ast.get_docstring(tree) or ""

        # Get top-level definitions
        definitions = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                definitions.append(f"class:{node.name}")
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                definitions.append(f"func:{node.name}")

        return docstring, definitions
    except Exception as e:
        return f"ERROR: {e}", []


def analyze_docstring_quality(
    docstring: str, definitions: list[str], filename: str
) -> dict:
    """Analyze if docstring is meaningful vs generic."""
    _ = filename  # Reserved for future __init__.py handling

    # Check for generic patterns
    generic_patterns = [
        "module.",
        "Package initialization.",
    ]

    is_generic = any(docstring.strip().endswith(p) for p in generic_patterns)
    is_empty = not docstring.strip()

    # Check if docstring mentions key concepts from definitions
    docstring_lower = docstring.lower()
    mentions_content = False
    for defn in definitions[:3]:  # Check first 3
        name = defn.split(":")[1].lower()
        # Convert CamelCase to words
        words = []
        current: list[str] = []
        for c in name:
            if c.isupper() and current:
                words.append("".join(current).lower())
                current = [c]
            else:
                current.append(c)
        if current:
            words.append("".join(current).lower())

        for word in words:
            if len(word) > 3 and word in docstring_lower:
                mentions_content = True
                break

    return {
        "is_empty": is_empty,
        "is_generic": is_generic,
        "mentions_content": mentions_content,
        "quality": "good"
        if (not is_empty and not is_generic)
        else ("generic" if is_generic else "empty"),
    }


def main():
    src_path = Path("src")
    results = {"good": [], "generic": [], "empty": [], "error": []}

    for py_file in sorted(src_path.rglob("*.py")):
        rel_path = py_file.relative_to(src_path)
        docstring, definitions = get_module_docstring(py_file)

        if docstring.startswith("ERROR:"):
            results["error"].append((str(rel_path), docstring))
            continue

        analysis = analyze_docstring_quality(docstring, definitions, py_file.name)
        quality = analysis["quality"]

        results[quality].append(
            {
                "path": str(rel_path),
                "docstring": docstring[:100] + "..."
                if len(docstring) > 100
                else docstring,
                "definitions": definitions[:5],
            }
        )

    # Print summary
    print("=" * 60)
    print("DOCSTRING VERIFICATION REPORT")
    print("=" * 60)
    print(f"\n✅ Good (detailed): {len(results['good'])}")
    print(f"⚠️  Generic: {len(results['generic'])}")
    print(f"❌ Empty: {len(results['empty'])}")
    print(f"🔴 Error: {len(results['error'])}")
    print(f"\nTotal: {sum(len(v) for v in results.values())}")

    # Show generic ones (need attention)
    if results["generic"]:
        print("\n" + "-" * 60)
        print("GENERIC DOCSTRINGS (need refinement):")
        print("-" * 60)
        for item in results["generic"]:
            print(f"\n📁 {item['path']}")
            print(f"   Doc: {item['docstring']}")
            if item["definitions"]:
                print(f"   Contains: {', '.join(item['definitions'][:3])}")

    # Show empty ones
    if results["empty"]:
        print("\n" + "-" * 60)
        print("EMPTY DOCSTRINGS:")
        print("-" * 60)
        for item in results["empty"]:
            print(f"📁 {item['path']}")


if __name__ == "__main__":
    main()
