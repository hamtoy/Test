"""Neo4j Rule/Constraint 최종 검증 스크립트.

Rule과 Constraint의 개수, ID, query_type 매핑이
의도한 대로 설정되었는지 최종 확인합니다.
"""

import os
import sys

from neo4j import GraphDatabase
from tabulate import tabulate


def final_verification():
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
            print("📊 최종 데이터베이스 상태 확인")
            print("=" * 70)

            # 1. Constraint 확인 (총 4개여야 함)
            print("\n1️⃣ Constraint 노드 (총 4개 예상)")
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.id as id, c.query_type as query_type, c.description as description
                ORDER BY c.id
            """)

            constraints = []
            for rec in result:
                constraints.append(
                    [
                        rec["id"],
                        rec["query_type"] or "NULL (Global)",
                        (rec["description"][:40] + "...")
                        if rec["description"]
                        else "N/A",
                    ]
                )

            print(
                tabulate(
                    constraints,
                    headers=["ID", "Query Type", "Description"],
                    tablefmt="simple",
                )
            )

            if len(constraints) == 4:
                print("\n✅ Constraint 개수 정상 (4개)")
            else:
                print(f"\n❌ Constraint 개수 비정상 ({len(constraints)}개)")

            # 2. Rule 확인 (총 138개 예상)
            print("\n2️⃣ Rule 노드 (총 138개 예상)")

            # 전체 개수
            count_res = session.run("MATCH (r:Rule) RETURN count(r) as cnt")
            total_rules = count_res.single()["cnt"]
            print(f"   총 Rule 개수: {total_rules}개")

            # query_type 속성이 있는 Rule (변환된 12개)
            print("\n   [속성 기반] query_type이 설정된 Rule (변환된 12개 예상):")
            result = session.run("""
                MATCH (r:Rule)
                WHERE r.query_type IS NOT NULL
                RETURN r.query_type as qt, count(*) as cnt
            """)
            for rec in result:
                print(f"   - {rec['qt']}: {rec['cnt']}개")

            # APPLIES_TO 관계로 연결된 Rule (기존 126개)
            print("\n   [관계 기반] APPLIES_TO로 연결된 Rule (기존 126개 예상):")
            result = session.run("""
                MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType)
                RETURN qt.name as qt_name, count(r) as cnt
                ORDER BY qt_name
            """)
            for rec in result:
                print(f"   - {rec['qt_name']}: {rec['cnt']}개")

            # 3. 템플릿 로드 시뮬레이션
            print("\n3️⃣ 템플릿 로드 시뮬레이션 (중복 제거 후 실제 사용 개수)")
            query_types = ["explanation", "summary", "reasoning", "target"]

            print(f"{'Query Type':<15} | {'Rules Count':<12}")
            print("-" * 30)

            for qt in query_types:
                # template_rules.py와 동일한 UNION 로직을 직접 실행해 개수를 센다.
                res = session.run(
                    """
                    MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
                    RETURN r.id
                    UNION
                    MATCH (r:Rule)
                    WHERE r.query_type = $qt
                    RETURN r.id
                """,
                    qt=qt,
                )

                count = len(list(res))
                print(f"{qt:<15} | {count:<12}")

    finally:
        driver.close()


if __name__ == "__main__":
    final_verification()
