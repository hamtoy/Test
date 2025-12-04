"""Neo4j 데이터베이스 전체 현황 확인 (간소화 버전)."""

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

try:
    with driver.session() as session:
        # 1. 전체 노드 개수
        print("=" * 70)
        print("📊 노드 타입별 개수")
        print("=" * 70)

        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as cnt
            ORDER BY cnt DESC
        """)

        for record in result:
            label = record["label"] or "NO_LABEL"
            cnt = record["cnt"]
            print(f"   {label:25} {cnt:5}개")

        # 2. query_type 속성 분포
        print(f"\n{'=' * 70}")
        print("📊 query_type 속성 분포")
        print("=" * 70)

        result = session.run("""
            MATCH (n)
            WHERE n.query_type IS NOT NULL
            RETURN labels(n)[0] as label, n.query_type as qt, count(*) as cnt
            ORDER BY label, qt
        """)

        current_label = None
        for record in result:
            label = record["label"]
            qt = record["qt"]
            cnt = record["cnt"]

            if label != current_label:
                print(f"\n{label}:")
                current_label = label

            print(f"   {qt:25} {cnt:3}개")

        # 3. Rule 노드 query_type 분포
        print(f"\n{'=' * 70}")
        print("📊 Rule 노드의 query_type")
        print("=" * 70)

        result = session.run("""
            MATCH (r:Rule)
            WITH r.query_type as qt
            RETURN qt, count(*) as cnt
            ORDER BY qt
        """)

        rule_found = False
        for record in result:
            qt = record["qt"] or "NULL"
            cnt = record["cnt"]
            print(f"   {qt:25} {cnt:3}개")
            rule_found = True

        if not rule_found:
            print("   (query_type 없음)")

        # 4. Constraint별 상세 (query_type 설정 여부)
        print(f"\n{'=' * 70}")
        print("📊 Constraint 노드 샘플 (최대 5개)")
        print("=" * 70)

        result = session.run("""
            MATCH (c:Constraint)
            RETURN c.id as id, c.query_type as qt, c.text as text
            LIMIT 5
        """)

        for record in result:
            node_id = record["id"] or "NULL"
            qt = record["qt"] or "NULL"
            text = record["text"]
            text_preview = (text[:40] + "...") if text else "N/A"

            print(f"\n   ID: {node_id}")
            print(f"   query_type: {qt}")
            print(f"   text: {text_preview}")

        # 5. 요약
        print(f"\n{'=' * 70}")
        print("💡 요약")
        print("=" * 70)

        # Constraint의 query_type 분포 확인
        result = session.run("""
            MATCH (c:Constraint)
            WHERE c.query_type IN ['summary', 'target_short', 'target_long']
            RETURN count(c) as cnt
        """)
        missing_cnt = result.single()["cnt"]

        if missing_cnt == 0:
            print(
                "\n⚠️  summary, target_short, target_long 타입의 Constraint 노드가 0개입니다."
            )
            print("\n원인:")
            print("   - 해당 query_type의 데이터가 아직 Neo4j에 임포트되지 않았습니다")
            print("   - Notion이나 다른 소스에 해당 데이터가 있는지 확인 필요")
            print("\n가능한 조치:")
            print("   1. src/graph/builder.py를 확인하여 데이터 임포트 로직 점검")
            print("   2. Notion 페이지에서 summary/target 관련 Constraint 확인")
            print("   3. 현재는 explanation/reasoning만 사용하도록 로직 조정")
        else:
            print(f"\n✅ summary/target 타입 Constraint: {missing_cnt}개 존재")

finally:
    driver.close()

print(f"\n{'=' * 70}")
