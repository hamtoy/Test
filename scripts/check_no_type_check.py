"""
@no_type_check 사용 탐지 스크립트

Usage:
    python scripts/check_no_type_check.py

This script finds all usages of @no_type_check decorator
and suggests alternatives for better type safety.
"""
from __future__ import annotations

import ast
from pathlib import Path


def find_no_type_check_usage(directory: Path) -> list[tuple[Path, int, str]]:
    """@no_type_check 데코레이터 사용 찾기"""
    results: list[tuple[Path, int, str]] = []

    for py_file in directory.rglob("*.py"):
        if "test_" in py_file.name:
            continue  # 테스트 파일은 제외

        try:
            with open(py_file) as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == "no_type_check":
                            results.append((py_file, node.lineno, node.name))

        except SyntaxError:
            pass

    return results


def main() -> None:
    """메인 실행"""
    src_dir = Path("src")

    usages = find_no_type_check_usage(src_dir)

    if not usages:
        print("✅ No @no_type_check decorators found!")
        return

    print(f"⚠️  Found {len(usages)} @no_type_check usages:\n")

    for file, line, func_name in usages:
        print(f"  📄 {file}:{line}")
        print(f"     Function: {func_name}")
        print("     👉 Consider using 'type: ignore' comments instead\n")

    print("\n💡 Alternatives:")
    print("  1. Use `# type: ignore[...]` for specific lines")
    print("  2. Create type stubs in stubs/ directory")
    print("  3. Add to mypy overrides if unavoidable")


if __name__ == "__main__":
    main()
