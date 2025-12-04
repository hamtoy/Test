"""템플릿 렌더링 테스트 스크립트.

Rule 객체(딕셔너리)와 문자열 Rule이 모두 올바르게 렌더링되는지 확인합니다.
"""

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_rendering():
    """템플릿 렌더링 테스트."""
    templates_dir = Path("c:/shining-quasar/templates/system/qa")
    env = Environment(loader=FileSystemLoader(str(templates_dir)))

    # 테스트할 템플릿
    template_name = "explanation.j2"
    template = env.get_template(template_name)

    print(f"🧪 템플릿 테스트: {template_name}")
    print("=" * 70)

    # Case 1: Rule이 딕셔너리인 경우 (Neo4j)
    rules_dict = [
        {"text": "Rule 1 from Neo4j", "priority": 100},
        {"text": "Rule 2 from Neo4j", "priority": 90},
    ]

    rendered_dict = template.render(
        rules=rules_dict,
        image_path="test.jpg",
        language_hint="Korean",
        text_density="High",
        has_table_chart=False,
    )

    print("\n[Case 1] Rule as Dict (Neo4j):")
    if (
        "- Rule 1 from Neo4j" in rendered_dict
        and "- Rule 2 from Neo4j" in rendered_dict
    ):
        print("✅ 성공! 딕셔너리 text 속성이 렌더링됨")
    else:
        print("❌ 실패! 렌더링 결과 확인 필요")
        print(rendered_dict[:500])

    # Case 2: Rule이 문자열인 경우 (Legacy)
    rules_str = ["Rule A (Legacy)", "Rule B (Legacy)"]

    rendered_str = template.render(
        rules=rules_str,
        image_path="test.jpg",
        language_hint="Korean",
        text_density="High",
        has_table_chart=False,
    )

    print("\n[Case 2] Rule as String (Legacy):")
    if "- Rule A (Legacy)" in rendered_str and "- Rule B (Legacy)" in rendered_str:
        print("✅ 성공! 문자열이 그대로 렌더링됨")
    else:
        print("❌ 실패! 렌더링 결과 확인 필요")
        print(rendered_str[:500])


if __name__ == "__main__":
    test_rendering()
