"""Neo4j 데이터베이스 전체 현황 확인 스크립트."""

import os
import sys

from neo4j import GraphDatabase


def check_database_status():
    """데이터베이스의 모든 노드 타입과 query_type 분포 확인."""
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
            print("📊 데이터베이스 전체 현황")
            print("=" * 70)

            # 1. 모든 노드 레이블과 개수
            print("\n1️⃣  전체 노드 타입별 개수:")
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as cnt
                ORDER BY cnt DESC
            """)

            total_nodes = 0
            for record in result:
                label = record["label"] or "NO_LABEL"
                cnt = record["cnt"]
                total_nodes += cnt
                print(f"   {label:20} {cnt:5}개")

            print(f"\n   {'총 노드':20} {total_nodes:5}개")

            # 2. query_type을 가진 노드들의 분포
            print(f"\n{'=' * 70}")
            print("2️⃣  query_type 속성을 가진 노드들:")
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
                    print(f"\n📁 {label}:")
                    current_label = label

                print(f"   {qt:20} {cnt:3}개")

            # 3. Constraint 노드 상세 확인
            print(f"\n{'=' * 70}")
            print("3️⃣  Constraint 노드 상세:")
            print("=" * 70)

            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.id as id, c.query_type as qt, c.text as text, c.priority as priority
                ORDER BY c.query_type, c.priority DESC
                LIMIT 20
            """)

            for record in result:
                node_id = record["id"] or "NULL"
                qt = record["qt"] or "NULL"
                text = record["text"]
                priority = record["priority"]

                text_preview = (text[:50] + "...") if text else "N/A"
                print(f"\n   ID: {node_id}")
                print(f"   Type: {qt}")
                print(f"   Priority: {priority or 'N/A'}")
                print(f"   Text: {text_preview}")

            # 4. Rule 노드 확인
            print(f"\n{'=' * 70}")
            print("4️⃣  Rule 노드 확인:")
            print("=" * 70)

            result = session.run("""
                MATCH (r:Rule)
                RETURN r.id as id, r.query_type as qt, count(*) as cnt
                RETURN DISTINCT r.query_type as qt, count(*) as cnt
                ORDER BY qt
            """)

            rule_types = list(result)
            if rule_types:
                for record in rule_types:
                    qt = record["qt"] or "NULL"
                    cnt = record["cnt"]
                    print(f"   {qt:20} {cnt:3}개")
            else:
                print("   Rule 노드가 없습니다.")

            # 5. 관계 확인
            print(f"\n{'=' * 70}")
            print("5️⃣  관계(Relationship) 현황:")
            print("=" * 70)

            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(*) as cnt
                ORDER BY cnt DESC
                LIMIT 10
            """)

            relationships = list(result)
            if relationships:
                for record in relationships:
                    rel_type = record["rel_type"]
                    cnt = record["cnt"]
                    print(f"   {rel_type:30} {cnt:5}개")
            else:
                print("   관계가 없습니다.")

            # 6. 필요한 데이터 체크
            print(f"\n{'=' * 70}")
            print("6️⃣  데이터 품질 체크:")
            print("=" * 70)

            # query_type별 Constraint 확인
            expected_types = [
                "explanation",
                "reasoning",
                "summary",
                "target_short",
                "target_long",
            ]

            for qt in expected_types:
                result = session.run(
                    "MATCH (c:Constraint {query_type: $qt}) RETURN count(c) as cnt",
                    qt=qt,
                )
                cnt = result.single()["cnt"]

                status = "✅" if cnt > 0 else "⚠️"
                print(f"   {status} {qt:20} {cnt:3}개")

            print(f"\n{'=' * 70}")
            print("💡 권장 사항:")
            print("=" * 70)

            # summary, target_short, target_long이 0개인 경우
            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IN ['summary', 'target_short', 'target_long']
                RETURN count(c) as cnt
            """)
            missing_cnt = result.single()["cnt"]

            if missing_cnt == 0:
                print(
                    "\n⚠️  summary, target_short, target_long 타입의 Constraint가 없습니다."
                )
                print("   다음 옵션을 고려하세요:")
                print("   1. Notion이나 다른 소스에서 해당 데이터를 임포트")
                print("   2. 기존 explanation/reasoning 제약사항을 재사용")
                print("   3. 새로운 제약사항을 수동으로 생성")
            else:
                print("\n✅ 모든 주요 query_type에 Constraint가 있습니다.")

    finally:
        driver.close()


if __name__ == "__main__":
    check_database_status()
