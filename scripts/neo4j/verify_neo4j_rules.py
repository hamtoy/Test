# scripts/verify_neo4j_rules.py (새 파일)
"""Neo4j 규칙 시스템 검증 스크립트"""

from src.qa.rag_system import QAKnowledgeGraph


def verify_rules():
    kg = QAKnowledgeGraph()

    types = ["target_short", "target_long", "explanation", "reasoning"]

    for qtype in types:
        print(f"\n{'=' * 60}")
        print(f"📋 {qtype} 타입")
        print("=" * 60)

        constraints = kg.get_constraints_for_query_type(qtype)

        if not constraints:
            print(f"⚠️  {qtype}에 대한 제약사항이 없습니다!")
            continue

        # category별 분류
        query_constraints = [
            c for c in constraints if c.get("category") in ["query", "both"]
        ]
        answer_constraints = [
            c for c in constraints if c.get("category") in ["answer", "both"]
        ]

        print(f"\n🔍 질의 제약사항 ({len(query_constraints)}개):")
        for c in sorted(
            query_constraints, key=lambda x: x.get("priority", 0), reverse=True
        ):
            print(f"  [{c.get('priority', 0)}] {c.get('name')}")
            print(f"      {c.get('description')[:80]}...")

        print(f"\n📝 답변 제약사항 ({len(answer_constraints)}개):")
        for c in sorted(
            answer_constraints, key=lambda x: x.get("priority", 0), reverse=True
        ):
            print(f"  [{c.get('priority', 0)}] {c.get('name')}")
            print(f"      {c.get('description')[:80]}...")


if __name__ == "__main__":
    verify_rules()
