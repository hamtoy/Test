"""Neo4j 인덱스 최적화 스크립트.

template_rules.py의 쿼리 성능을 개선하기 위해
필요한 인덱스를 생성하고 캐시 워밍업을 수행합니다.
"""

import os
import sys

from neo4j import GraphDatabase


def run_optimization():
    """Neo4j 인덱스 최적화 실행."""
    # 환경 변수에서 Neo4j 접속 정보 가져오기
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        print(
            "   NEO4J_URI, NEO4J_USERNAME (또는 NEO4J_USER), NEO4J_PASSWORD를 설정하세요."
        )
        sys.exit(1)

    print(f"🔗 Neo4j 연결 중: {uri}")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session() as session:
            print("\n📊 인덱스 생성 시작...")

            # 1. Constraint 인덱스
            print("  - Constraint.query_type 인덱스 생성 중...")
            session.run(
                "CREATE INDEX constraint_type_idx IF NOT EXISTS "
                "FOR (c:Constraint) ON (c.query_type)"
            )

            # 2. FormattingRule 인덱스
            print("  - FormattingRule.query_type 인덱스 생성 중...")
            session.run(
                "CREATE INDEX formatting_type_idx IF NOT EXISTS "
                "FOR (f:FormattingRule) ON (f.query_type)"
            )

            # 3. BestPractice 인덱스
            print("  - BestPractice.query_type 인덱스 생성 중...")
            session.run(
                "CREATE INDEX best_practice_type_idx IF NOT EXISTS "
                "FOR (b:BestPractice) ON (b.query_type)"
            )

            # 4. Rule 인덱스
            print("  - Rule.query_type 인덱스 생성 중...")
            session.run(
                "CREATE INDEX rule_type_idx IF NOT EXISTS "
                "FOR (r:Rule) ON (r.query_type)"
            )

            print("\n✅ 인덱스 생성 완료!")

            # 인덱스 상태 확인
            print("\n📋 생성된 인덱스 목록:")
            result = session.run("SHOW INDEXES")
            for record in result:
                index_name = record.get("name", "N/A")
                index_type = record.get("type", "N/A")
                state = record.get("state", "N/A")
                print(f"  - {index_name} ({index_type}): {state}")

            # 캐시 워밍업
            print("\n🔥 캐시 워밍업 중...")

            print("  - Constraint 노드 조회...")
            result = session.run(
                "MATCH (c:Constraint) "
                "RETURN c.query_type, count(*) as cnt "
                "ORDER BY cnt DESC"
            )
            for record in result:
                print(f"    {record['c.query_type']}: {record['cnt']}개")

            print("  - FormattingRule 노드 조회...")
            result = session.run(
                "MATCH (f:FormattingRule) "
                "RETURN f.query_type, count(*) as cnt "
                "ORDER BY cnt DESC"
            )
            for record in result:
                print(f"    {record['f.query_type']}: {record['cnt']}개")

            print("\n✅ 최적화 완료!")
            print("\n💡 다음 단계:")
            print("  1. template_rules.py의 쿼리가 이제 더 빠르게 실행됩니다.")
            print("  2. 성능 측정을 위해 애플리케이션을 실행해보세요.")

    finally:
        driver.close()


if __name__ == "__main__":
    run_optimization()
