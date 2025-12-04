"""변환된 Rule 노드와 사용처 확인 스크립트."""

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
        print("=" * 70)
        print("📊 변환된 Rule 노드 확인")
        print("=" * 70)

        # 변환된 Rule (converted_from 속성 있음)
        result = session.run("""
            MATCH (r:Rule)
            WHERE r.converted_from = 'Constraint'
            RETURN r.id as id,
                   r.text as text,
                   r.query_type as qt,
                   r.priority as priority,
                   r.converted_at as converted_at
            ORDER BY r.priority DESC
            LIMIT 5
        """)

        converted = list(result)
        print(f"\n변환된 Rule (converted_from='Constraint'): {len(converted)}개 샘플\n")

        for i, rec in enumerate(converted, 1):
            text = (
                (rec["text"][:60] + "...")
                if rec["text"] and len(rec["text"]) > 60
                else rec["text"]
            )
            print(f"[{i}] {rec['id']}")
            print(f"    query_type: {rec['qt']}")
            print(f"    priority: {rec['priority']}")
            print(f"    text: {text}")
            print(f"    converted_at: {rec['converted_at']}\n")

        # 전체 Rule 통계
        print("=" * 70)
        print("📊 전체 Rule 노드 통계")
        print("=" * 70)

        result = session.run("""
            MATCH (r:Rule)
            RETURN 
                count(r) as total,
                count(CASE WHEN r.converted_from = 'Constraint' THEN 1 END) as converted,
                count(CASE WHEN r.query_type IS NOT NULL THEN 1 END) as with_qt,
                count(CASE WHEN r.query_type IS NULL THEN 1 END) as without_qt
        """)

        stats = result.single()
        print(f"\n총 Rule 노드: {stats['total']}개")
        print(f"  - Constraint에서 변환: {stats['converted']}개")
        print(f"  - query_type 있음: {stats['with_qt']}개")
        print(f"  - query_type 없음: {stats['without_qt']}개")

        # query_type 분포
        print("\nquery_type 분포:")
        result = session.run("""
            MATCH (r:Rule)
            WHERE r.query_type IS NOT NULL
            RETURN r.query_type as qt, count(*) as cnt
            ORDER BY cnt DESC
        """)

        for rec in result:
            print(f"  - {rec['qt']}: {rec['cnt']}개")

        # Rule의 관계 확인
        print(f"\n{'=' * 70}")
        print("🔗 Rule 노드의 관계")
        print("=" * 70)

        # Incoming 관계
        result = session.run("""
            MATCH (n)-[r]->(rule:Rule)
            RETURN type(r) as rel_type, labels(n)[0] as from_label, count(*) as cnt
            ORDER BY cnt DESC
            LIMIT 5
        """)

        incoming = list(result)
        if incoming:
            print("\nIncoming 관계 (→ Rule):")
            for rec in incoming:
                print(
                    f"  {rec['from_label']} -[{rec['rel_type']}]→ Rule: {rec['cnt']}개"
                )
        else:
            print("\nIncoming 관계: 없음")

        # Outgoing 관계
        result = session.run("""
            MATCH (rule:Rule)-[r]->(n)
            RETURN type(r) as rel_type, labels(n)[0] as to_label, count(*) as cnt
            ORDER BY cnt DESC
            LIMIT 5
        """)

        outgoing = list(result)
        if outgoing:
            print("\nOutgoing 관계 (Rule →):")
            for rec in outgoing:
                print(f"  Rule -[{rec['rel_type']}]→ {rec['to_label']}: {rec['cnt']}개")
        else:
            print("\nOutgoing 관계: 없음")

finally:
    driver.close()

print(f"\n{'=' * 70}")
print("💡 참고")
print("=" * 70)
print("\n현재 template_rules.py는 Rule이 아닌 Item 노드를 사용합니다:")
print("  - get_rules_for_query_type() → Item 노드 조회")
print("  - 템플릿 변수 'guide_rules' → Item에서 가져옴")
print("\nRule 노드를 템플릿에서 사용하려면:")
print("  1. template_rules.py에 Rule 조회 함수 추가")
print("  2. 템플릿(*.j2)에서 새 변수 사용")
print("  3. generator.py에서 컨텍스트 전달")
