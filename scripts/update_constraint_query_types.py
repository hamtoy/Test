"""기존 Constraint 노드에 query_type 재설정 스크립트.

TEMPLATES의 enforces 관계를 분석하여 각 Constraint의 query_type을
자동으로 설정합니다. (builder.py 로직과 동일)
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase

from src.graph.schema import CONSTRAINTS, TEMPLATES


def update_constraint_query_types():
    """기존 Constraint 노드의 query_type 업데이트."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 Neo4j 연결: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        # 1. Constraint-QueryType 매핑 생성
        print("=" * 70)
        print("📊 Template-Constraint 매핑 분석")
        print("=" * 70)

        constraint_to_query_types = {}

        for template in TEMPLATES:
            template_name = template["name"]
            query_type = template_name.split("_")[0]

            print(f"\n{template_name} ({query_type}):")
            for constraint_id in template.get("enforces", []):
                if constraint_id not in constraint_to_query_types:
                    constraint_to_query_types[constraint_id] = []
                if query_type not in constraint_to_query_types[constraint_id]:
                    constraint_to_query_types[constraint_id].append(query_type)

                print(f"   - {constraint_id}")

        # 2. 추론 결과 출력
        print(f"\n{'=' * 70}")
        print("🎯 추론된 query_type")
        print("=" * 70)

        updates = []
        for constraint_id in [c["id"] for c in CONSTRAINTS]:
            query_types = constraint_to_query_types.get(constraint_id, [])

            if not query_types:
                query_type = None
                status = "전역 (사용되지 않음)"
            elif len(query_types) >= 3:
                query_type = None
                status = f"전역 (사용: {', '.join(query_types)})"
            else:
                query_type = query_types[0]
                status = f"{query_type} (사용: {', '.join(query_types)})"

            updates.append((constraint_id, query_type))
            print(f"   {constraint_id:30} -> {status}")

        # 3. 업데이트 실행
        print(f"\n{'=' * 70}")
        print("🚀 Neo4j 업데이트 실행")
        print("=" * 70)

        with driver.session() as session:
            for constraint_id, query_type in updates:
                session.run(
                    """
                    MATCH (c:Constraint {id: $id})
                    SET c.query_type = $query_type
                    """,
                    id=constraint_id,
                    query_type=query_type,
                )

                qt_display = query_type or "NULL"
                print(f"   ✓ {constraint_id} -> {qt_display}")

        print(f"\n✅ {len(updates)}개 Constraint 업데이트 완료!")

        # 4. 검증
        print(f"\n{'=' * 70}")
        print("🔍 검증")
        print("=" * 70)

        with driver.session() as session:
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.query_type as qt, count(*) as cnt
                ORDER BY qt
            """)

            print("\n현재 query_type 분포:")
            for record in result:
                qt = record["qt"] or "NULL (전역)"
                cnt = record["cnt"]
                print(f"   {qt:20} {cnt:3}개")

    finally:
        driver.close()


if __name__ == "__main__":
    update_constraint_query_types()
