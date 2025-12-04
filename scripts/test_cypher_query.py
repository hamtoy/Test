"""Cypher 쿼리 직접 테스트."""

import os
import sys
from typing import Optional

from neo4j import GraphDatabase

uri: Optional[str] = os.getenv("NEO4J_URI")
username: Optional[str] = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
password: Optional[str] = os.getenv("NEO4J_PASSWORD")

if not uri or not username or not password:
    print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
    sys.exit(1)

print(f"🔗 Neo4j 연결: {uri}\n")
driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session() as session:
        print("=" * 70)
        print("🧪 Cypher 쿼리 테스트")
        print("=" * 70)

        query_type = "explanation"

        # 1. QueryType 노드 존재 확인
        print(f"\n1️⃣ QueryType 노드 확인 (name='{query_type}'):")
        result = session.run(
            """
            MATCH (qt:QueryType {name: $qt})
            RETURN qt.name as name, qt.korean as korean
        """,
            qt=query_type,
        )

        qt_node = result.single()
        if qt_node:
            print(f"   ✅ 존재: {qt_node['name']} ({qt_node['korean']})")
        else:
            print("   ❌ 없음!")

        # 2. APPLIES_TO 관계 확인
        print("\n2️⃣ Rule -[:APPLIES_TO]→ QueryType 관계:")
        result = session.run(
            """
            MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
            RETURN count(r) as cnt
        """,
            qt=query_type,
        )

        cnt_record = result.single()
        cnt = cnt_record["cnt"] if cnt_record else 0
        print(f"   {cnt}개")

        if cnt > 0:
            result = session.run(
                """
                MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
                RETURN r.id as id, r.text as text, r.query_type as qt
                LIMIT 3
            """,
                qt=query_type,
            )

            print("\n   샘플:")
            for rec in result:
                text = (rec["text"][:40] + "...") if rec["text"] else "N/A"
                print(f"     - {rec['id']}: {text}")

        # 3. applies_to 속성 확인
        print("\n3️⃣ Rule.applies_to 속성:")
        result = session.run(
            """
            MATCH (r:Rule)
            WHERE r.applies_to IN ['all', $qt]
            RETURN count(r) as cnt
        """,
            qt=query_type,
        )

        cnt_record = result.single()
        cnt = cnt_record["cnt"] if cnt_record else 0
        print(f"   {cnt}개")

        if cnt > 0:
            result = session.run(
                """
                MATCH (r:Rule)
                WHERE r.applies_to IN ['all', $qt]
                RETURN r.id as id, r.applies_to as applies_to, r.text as text
                LIMIT 3
            """,
                qt=query_type,
            )

            print("\n   샘플:")
            for rec in result:
                text = (rec["text"][:40] + "...") if rec["text"] else "N/A"
                print(f"     - {rec['id']} (applies_to={rec['applies_to']}): {text}")

        # 4. query_type 속성 확인 (변환된 Rule)
        print("\n4️⃣ Rule.query_type 속성:")
        result = session.run(
            """
            MATCH (r:Rule)
            WHERE r.query_type = $qt
            RETURN count(r) as cnt
        """,
            qt=query_type,
        )

        cnt_record = result.single()
        cnt = cnt_record["cnt"] if cnt_record else 0
        print(f"   {cnt}개")

        if cnt > 0:
            result = session.run(
                """
                MATCH (r:Rule)
                WHERE r.query_type = $qt
                RETURN r.id as id, r.text as text, r.priority as priority
                ORDER BY r.priority DESC
                LIMIT 3
            """,
                qt=query_type,
            )

            print("\n   샘플:")
            for rec in result:
                text = (rec["text"][:40] + "...") if rec["text"] else "N/A"
                print(f"     - {rec['id']} (priority={rec['priority']}): {text}")

        # 5. template_rules.py의 Cypher 쿼리 테스트
        print("\n5️⃣ template_rules.py의 Cypher 쿼리:")
        cypher = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (r:Rule)-[:APPLIES_TO]->(qt)
        WITH qt, collect(r) AS rules_rel
        OPTIONAL MATCH (r2:Rule)
        WHERE r2.applies_to IN ['all', $qt]
        WITH qt, rules_rel + collect(r2) AS rules
        UNWIND rules AS r
        WITH DISTINCT r
        RETURN
            coalesce(r.name, '') AS name,
            coalesce(r.text, '') AS text,
            coalesce(r.category, '') AS category,
            coalesce(r.priority, 0) AS priority
        ORDER BY priority DESC
        """

        result = session.run(cypher, qt=query_type)
        records = list(result)
        print(f"   결과: {len(records)}개")

        if records:
            print("\n   샘플:")
            for i, rec in enumerate(records[:3], 1):
                text = (rec["text"][:40] + "...") if rec["text"] else "N/A"
                print(f"     [{i}] priority={rec['priority']}: {text}")

finally:
    driver.close()

print(f"\n{'=' * 70}")
