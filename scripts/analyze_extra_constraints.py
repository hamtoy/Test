"""추가 Constraint 노드 상세 분석 스크립트.

schema.py에 정의된 4개 외 12개 노드가 어디서 왔는지 확인.
"""

import os
import sys

from neo4j import GraphDatabase

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

if not all([uri, username, password]):
    print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
    sys.exit(1)

print(f"🔗 Neo4j 연결: {uri}\n")
driver = GraphDatabase.driver(uri, auth=(username, password))

# schema.py에 정의된 공식 Constraint ID들
OFFICIAL_IDS = {
    "session_turns",
    "explanation_summary_limit",
    "calculation_limit",
    "table_chart_prohibition",
}

try:
    with driver.session() as session:
        print("=" * 70)
        print("📊 전체 Constraint 노드 분석")
        print("=" * 70)

        # 모든 Constraint 노드 조회
        result = session.run("""
            MATCH (c:Constraint)
            RETURN c.id as id,
                   c.description as description,
                   c.type as type,
                   c.query_type as query_type,
                   c.text as text,
                   c.priority as priority,
                   c.extracted_at as extracted_at,
                   properties(c) as all_props
            ORDER BY c.id
        """)

        official_nodes = []
        extra_nodes = []

        for record in result:
            node_id = record["id"]

            node_info = {
                "id": node_id or "NULL",
                "description": record["description"],
                "type": record["type"],
                "query_type": record["query_type"],
                "text": record["text"],
                "priority": record["priority"],
                "extracted_at": record["extracted_at"],
                "all_props": record["all_props"],
            }

            if node_id in OFFICIAL_IDS:
                official_nodes.append(node_info)
            else:
                extra_nodes.append(node_info)

        # 공식 노드 출력
        print(f"\n✅ schema.py에 정의된 공식 Constraint: {len(official_nodes)}개")
        print("=" * 70)
        for node in official_nodes:
            print(f"\nID: {node['id']}")
            print(f"  description: {node['description']}")
            print(f"  type: {node['type']}")
            print(f"  query_type: {node['query_type'] or 'NULL'}")

        # 추가 노드 출력
        print(f"\n⚠️  추가로 발견된 Constraint: {len(extra_nodes)}개")
        print("=" * 70)

        if not extra_nodes:
            print("\n(추가 노드 없음)")
        else:
            for i, node in enumerate(extra_nodes, 1):
                print(f"\n[{i}] ID: {node['id']}")
                print(f"    description: {node['description'] or 'N/A'}")
                print(f"    type: {node['type'] or 'N/A'}")
                print(f"    query_type: {node['query_type'] or 'NULL'}")
                print(
                    f"    text: {(node['text'][:50] + '...') if node['text'] else 'N/A'}"
                )
                print(f"    priority: {node['priority'] or 'N/A'}")
                print(f"    extracted_at: {node['extracted_at'] or 'N/A'}")

                # 전체 속성 확인
                print(f"    모든 속성: {list(node['all_props'].keys())}")

        # 관계 확인
        print(f"\n{'=' * 70}")
        print("🔗 추가 노드의 관계 확인")
        print("=" * 70)

        if extra_nodes:
            extra_ids = [n["id"] for n in extra_nodes if n["id"] != "NULL"]

            if extra_ids:
                for node_id in extra_ids[:3]:  # 처음 3개만
                    print(f"\n{node_id}의 관계:")

                    # Incoming
                    result = session.run(
                        """
                        MATCH (n)-[r]->(c:Constraint {id: $id})
                        RETURN labels(n) as from_labels, type(r) as rel_type
                        LIMIT 3
                    """,
                        id=node_id,
                    )

                    incoming = list(result)
                    if incoming:
                        for rec in incoming:
                            print(f"  ← {rec['from_labels']} -[{rec['rel_type']}]→")

                    # Outgoing
                    result = session.run(
                        """
                        MATCH (c:Constraint {id: $id})-[r]->(n)
                        RETURN labels(n) as to_labels, type(r) as rel_type
                        LIMIT 3
                    """,
                        id=node_id,
                    )

                    outgoing = list(result)
                    if outgoing:
                        for rec in outgoing:
                            print(f"  → -[{rec['rel_type']}]→ {rec['to_labels']}")

                    if not incoming and not outgoing:
                        print("  (관계 없음)")

            # NULL ID 노드 확인
            null_count = sum(1 for n in extra_nodes if n["id"] == "NULL")
            if null_count > 0:
                print(f"\n⚠️  ID가 NULL인 노드: {null_count}개")
                print("   이 노드들은 고유 식별자가 없어 추적이 어렵습니다.")

        # 결론
        print(f"\n{'=' * 70}")
        print("💡 결론")
        print("=" * 70)

        if len(extra_nodes) == 0:
            print("\n✅ schema.py의 4개 Constraint만 존재합니다. 정상입니다!")
        else:
            print(
                f"\n⚠️  schema.py에 정의되지 않은 {len(extra_nodes)}개의 Constraint가 있습니다."
            )
            print("\n가능한 원인:")
            print("  1. 이전 데이터 임포트 시 Rule이 Constraint로 잘못 분류됨")
            print("  2. 수동으로 추가한 테스트 데이터")
            print("  3. fix_constraint_query_types.py가 생성한 데이터")
            print("  4. Notion 문서에서 추출 시 과도하게 생성됨")
            print("\n권장 조치:")
            print("  - 필요없는 노드라면 삭제")
            print("  - 유용한 노드라면 schema.py에 추가")
            print("  - 또는 Rule 노드로 재분류")

finally:
    driver.close()
