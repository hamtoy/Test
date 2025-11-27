"""
Level 1 에러 자동 수정 도우미
"""

import re
import sys
from pathlib import Path


def add_return_type_hints(filepath: Path) -> int:
    """
    함수에 -> None 또는 -> Any 추가

    Before:
        def process_data(self, data):
            ...

    After:
        def process_data(self, data) -> None:
            ...
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    changes = 0
    lines = content.split("\n")
    new_lines: list[str] = []

    for i, line in enumerate(lines):
        # def function_name(...):
        match = re.match(r"^(\s*def\s+\w+\s*\([^)]*\))\s*:(.*)$", line)

        if match and "->" not in line:
            # 다음 줄 확인 (docstring or pass or return)
            next_line = lines[i + 1] if i + 1 < len(lines) else ""

            if "return" in next_line or "yield" in next_line:
                # 실제 반환값 있음 → Any 사용 (수동 수정 필요)
                new_line = f"{match.group(1)} -> Any:{match.group(2)}"
            else:
                # 반환값 없음 → None
                new_line = f"{match.group(1)} -> None:{match.group(2)}"

            new_lines.append(new_line)
            changes += 1
        else:
            new_lines.append(line)

    if changes > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))

    return changes


def add_variable_annotations(filepath: Path) -> int:
    """
    변수에 타입 힌트 추가

    Before:
        items = []

    After:
        items: List[Any] = []
    """
    # 단순 패턴만 처리 (복잡한 경우 수동)
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # NOTE: 구현 생략 (실제로는 AST 파싱 필요)
    _ = content
    changes = 0

    return changes


def process_file(filepath: Path) -> tuple[int, int]:
    """파일 처리"""
    return_types = add_return_type_hints(filepath)
    var_annotations = add_variable_annotations(filepath)

    return return_types, var_annotations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/fix_mypy_level1.py src/agent/core.py")
        sys.exit(1)

    target_filepath = Path(sys.argv[1])
    returns, vars_count = process_file(target_filepath)

    print(f"✅ {target_filepath}")
    print(f"   - Return types added: {returns}")
    print(f"   - Variable annotations: {vars_count}")
