"""template_rules.get_all_template_context() 테스트."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.qa.template_rules import get_all_template_context, get_neo4j_config


def test_template_context():
    """템플릿 컨텍스트에 rules가 포함되는지 테스트."""

    # Neo4j 설정 가져오기
    config = get_neo4j_config()

    print("=" * 70)
    print("🧪 template_rules.get_all_template_context() 테스트")
    print("=" * 70)

    # explanation 타입으로 테스트
    query_types = ["explanation", "summary", "reasoning", "target"]

    for qt in query_types:
        print(f"\n📊 query_type: {qt}")
        print("-" * 70)

        try:
            context = get_all_template_context(
                query_type=qt,
                neo4j_uri=config["neo4j_uri"],
                neo4j_user=config["neo4j_user"],
                neo4j_password=config["neo4j_password"],
                include_mistakes=True,
                include_best_practices=False,
                include_constraints=False,
                context_stage="answer",
            )

            # rules 확인
            rules = context.get("rules", [])
            print(f"✅ rules 개수: {len(rules)}개")

            if rules:
                print("\n샘플 (최대 3개):")
                for i, rule in enumerate(rules[:3], 1):
                    name = rule.get("name", "N/A")
                    text = rule.get("text", "")
                    priority = rule.get("priority", 0)
                    category = rule.get("category", "N/A")

                    text_preview = (text[:50] + "...") if len(text) > 50 else text

                    print(f"\n  [{i}] {name}")
                    print(f"      category: {category}")
                    print(f"      priority: {priority}")
                    print(f"      text: {text_preview}")

            # guide_rules 확인 (Item 노드)
            guide_rules = context.get("guide_rules", [])
            print(f"\n📚 guide_rules 개수: {len(guide_rules)}개 (Item 노드)")

        except Exception as e:
            print(f"❌ 오류: {e}")

    print(f"\n{'=' * 70}")
    print("✅ 테스트 완료!")
    print("=" * 70)
    print("\n💡 결과:")
    print("  - rules: Rule 노드에서 조회 (새로 추가)")
    print("  - guide_rules: Item 노드에서 조회 (기존)")
    print("\n두 가지 소스를 모두 템플릿에서 사용할 수 있습니다!")


if __name__ == "__main__":
    test_template_context()
