"""테스트 타입 힌트 체크리스트.

테스트 파일의 타입 힌트 누락을 확인하고 보고합니다.

사용법:
    python scripts/check_test_types.py

수정 후 검증:
    mypy tests/test_agent.py --strict
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def check_test_file(file_path: Path) -> list[str]:
    """테스트 파일의 타입 힌트 누락 확인.

    Args:
        file_path: 검사할 테스트 파일 경로

    Returns:
        발견된 이슈 목록
    """
    issues: list[str] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
    except SyntaxError as e:
        return [f"구문 오류: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # 테스트 함수와 fixture만 체크
            if not (
                node.name.startswith("test_") or _has_pytest_fixture_decorator(node)
            ):
                continue

            # 반환 타입 체크
            if node.returns is None:
                issues.append(f"{node.name}: 반환 타입 없음 (→ None 추가 권장)")

            # 파라미터 타입 체크
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    issues.append(f"{node.name}: '{arg.arg}' 파라미터 타입 없음")

    return issues


def _has_pytest_fixture_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """pytest.fixture 데코레이터가 있는지 확인."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "fixture":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
            return True
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name) and decorator.func.id == "fixture":
                return True
            if (
                isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "fixture"
            ):
                return True
    return False


def main() -> int:
    """모든 테스트 파일 체크."""
    # 프로젝트 루트 찾기
    project_root = Path(__file__).resolve().parents[1]
    test_dir = project_root / "tests"

    if not test_dir.exists():
        print(f"❌ 테스트 디렉토리를 찾을 수 없습니다: {test_dir}")
        return 1

    total_issues = 0
    files_with_issues = 0

    # 테스트 파일 검사
    test_files = sorted(test_dir.glob("test_*.py"))

    if not test_files:
        print("⚠️ 테스트 파일을 찾을 수 없습니다")
        return 0

    print("🔍 테스트 파일 타입 힌트 검사 중...\n")

    for test_file in test_files:
        issues = check_test_file(test_file)
        if issues:
            files_with_issues += 1
            print(f"📄 {test_file.name}")
            for issue in issues:
                print(f"  ⚠️  {issue}")
            total_issues += len(issues)

    # 요약 출력
    print("\n" + "=" * 50)
    print(f"📊 검사 완료: {len(test_files)}개 파일")
    print(f"   이슈 파일: {files_with_issues}개")
    print(f"   총 이슈: {total_issues}개")

    if total_issues > 0:
        print("\n💡 수정 후 다시 실행:")
        print("   python scripts/check_test_types.py")
        print("\n🔧 특정 파일 검증:")
        print("   mypy tests/test_agent.py --strict")
    else:
        print("\n✅ 모든 테스트 파일이 타입 힌트를 가지고 있습니다!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
