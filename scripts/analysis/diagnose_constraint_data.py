"""Constraint 노드 데이터 품질 진단 스크립트.

NULL query_type을 가진 Constraint 노드를 분석하고
적절한 query_type 값을 제안합니다.
"""

import os
import sys

from neo4j import GraphDatabase


def diagnose_constraints():
    """Constraint 노드 진단."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 Neo4j 연결 중: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session() as session:
            print("=" * 70)
            print("📊 Constraint 노드 분석")
            print("=" * 70)

            # 전체 Constraint 노드 개수
            result = session.run("MATCH (c:Constraint) RETURN count(c) as total")
            total = result.single()["total"]
            print(f"\n총 Constraint 노드: {total}개")

            # NULL query_type 개수
            result = session.run(
                "MATCH (c:Constraint) WHERE c.query_type IS NULL RETURN count(c) as null_count"
            )
            null_count = result.single()["null_count"]
            print(f"NULL query_type: {null_count}개")

            if null_count == 0:
                print("\n✅ 모든 Constraint 노드에 query_type이 설정되어 있습니다!")
                return

            # NULL인 노드들의 속성 확인
            print(f"\n{'=' * 70}")
            print("🔍 NULL query_type 노드 샘플 (최대 10개)")
            print("=" * 70)

            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IS NULL
                RETURN c.id as id, c.text as text, c.priority as priority
                LIMIT 10
            """)

            nodes = []
            for i, record in enumerate(result, 1):
                node_id = record["id"]
                text = record["text"]
                priority = record["priority"]

                print(f"\n[{i}] ID: {node_id}")
                print(f"    Text: {text[:100] if text else 'N/A'}...")
                print(f"    Priority: {priority or 'N/A'}")

                nodes.append({"id": node_id, "text": text, "priority": priority})

            # 다른 노드 타입과의 관계 확인
            print(f"\n{'=' * 70}")
            print("🔗 관계 분석")
            print("=" * 70)

            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IS NULL
                OPTIONAL MATCH (c)-[r]->(n)
                RETURN type(r) as rel_type, labels(n) as target_labels, count(*) as cnt
                ORDER BY cnt DESC
                LIMIT 5
            """)

            print("\nConstraint 노드의 outgoing 관계:")
            for record in result:
                rel_type = record["rel_type"] or "없음"
                target_labels = record["target_labels"] or []
                cnt = record["cnt"]
                print(f"  - {rel_type} -> {target_labels}: {cnt}개")

            # 모든 query_type 값 확인
            print(f"\n{'=' * 70}")
            print("📝 기존 query_type 값 목록")
            print("=" * 70)

            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IS NOT NULL
                RETURN DISTINCT c.query_type as qt, count(*) as cnt
                ORDER BY cnt DESC
            """)

            existing_types = []
            for record in result:
                qt = record["qt"]
                cnt = record["cnt"]
                existing_types.append(qt)
                print(f"  - {qt}: {cnt}개")

            if not existing_types:
                print("\n⚠️  기존에 설정된 query_type이 없습니다.")
                print("   표준 query_type 목록:")
                print("   - explanation")
                print("   - reasoning")
                print("   - summary")
                print("   - target_short")
                print("   - target_long")

            print(f"\n{'=' * 70}")
            print("💡 권장 조치")
            print("=" * 70)
            print("\n1. 수동 분류가 필요한 경우:")
            print("   - Neo4j Browser에서 각 노드를 확인하고 적절한 query_type 설정")
            print(
                "   - 예: MATCH (c:Constraint {id: 'xxx'}) SET c.query_type = 'explanation'"
            )

            print("\n2. 일괄 처리가 가능한 경우:")
            print("   - 모든 NULL 노드를 기본값으로 설정")
            print(
                "   - 예: MATCH (c:Constraint) WHERE c.query_type IS NULL SET c.query_type = 'explanation'"
            )

            print("\n3. 자동 분류 스크립트 실행:")
            print("   - python scripts/fix_constraint_query_types.py")

    finally:
        driver.close()


if __name__ == "__main__":
    diagnose_constraints()
