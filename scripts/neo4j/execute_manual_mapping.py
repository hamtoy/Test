"""
Neo4j Aura 수동 매핑 실행
MANUAL_MAPPING_GUIDE.md에 정의된 매핑을 실제로 실행
"""

import os

from neo4j import GraphDatabase


class ManualMapper:
    """수동 매핑 실행기"""

    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def execute_mapping(self):
        """모든 매핑 실행"""

        print("=" * 70)
        print("Neo4j Aura 수동 매핑 실행")
        print("=" * 70)

        with self.driver.session() as session:
            # 1. QueryType 매핑
            print("\n1️⃣  Item → QueryType 매핑 실행...")
            print("-" * 70)

            mappings = [
                ("설명문 질의", "explanation"),
                ("추론 질의", "reasoning"),
                ("이미지 내 타겟 질의", "target_short"),
                ("요약문 질의", "target_long"),
            ]

            total_created = 0
            for item_keyword, qt_name in mappings:
                result = session.run(
                    """
                    MATCH (i:Item)
                    WHERE i.name CONTAINS $keyword
                    WITH i LIMIT 1
                    MATCH (qt:QueryType {name: $qt_name})
                    MERGE (i)-[r:DESCRIBES_QUERY_TYPE]->(qt)
                    RETURN count(r) as created
                """,
                    keyword=item_keyword,
                    qt_name=qt_name,
                )

                count = result.single()
                if count and count["created"] > 0:
                    print(f"  ✓ '{item_keyword}' → QueryType.{qt_name}")
                    total_created += count["created"]

            print(f"\n  총 {total_created}개 연결 생성")

            # 2. 작업 규칙 Item에 태그 추가
            print("\n2️⃣  작업 규칙 Item에 GuideRule 태그 추가...")
            print("-" * 70)

            result = session.run("""
                MATCH (i:Item)
                WHERE i.categoryName = "작업 규칙"
                SET i:GuideRule
                RETURN count(i) as tagged
            """)

            count = result.single()["tagged"]
            print(f"  ✓ {count}개 Item에 GuideRule 태그 추가됨")

            # 3. 예시 포함 QATopic 태그 추가
            print("\n3️⃣  예시 포함 QATopic에 ContainsExample 태그 추가...")
            print("-" * 70)

            result = session.run("""
                MATCH (t:QATopic)
                WHERE t.content CONTAINS "예시"
                   OR t.content CONTAINS "❌"
                   OR t.content CONTAINS "⭕"
                SET t:ContainsExample
                RETURN count(t) as tagged
            """)

            count = result.single()["tagged"]
            print(f"  ✓ {count}개 Topic에 ContainsExample 태그 추가됨")

            # 4. 제약조건 관련 Item 태그
            print("\n4️⃣  제약조건 관련 Item에 ConstraintRelated 태그...")
            print("-" * 70)

            result = session.run("""
                MATCH (i:Item)
                WHERE i.content CONTAINS "불가" 
                   OR i.content CONTAINS "금지"
                   OR i.content CONTAINS "반드시"
                   OR i.content CONTAINS "지양"
                SET i:ConstraintRelated
                RETURN count(i) as tagged
            """)

            count = result.single()["tagged"]
            print(f"  ✓ {count}개 Item에 ConstraintRelated 태그 추가됨")

            # 5. Best Practice 관련 Item 태그
            print("\n5️⃣  Best Practice 관련 Item에 BestPracticeRelated 태그...")
            print("-" * 70)

            result = session.run("""
                MATCH (i:Item)
                WHERE i.content CONTAINS "지향"
                   OR i.content CONTAINS "권장"
                   OR i.name CONTAINS "주의사항"
                SET i:BestPracticeRelated
                RETURN count(i) as tagged
            """)

            count = result.single()["tagged"]
            print(f"  ✓ {count}개 Item에 BestPracticeRelated 태그 추가됨")

            # 6. 키워드 기반 Item-Rule 관계 생성
            print("\n6️⃣  키워드 기반 Item → Rule 관계 생성...")
            print("-" * 70)

            result = session.run("""
                MATCH (i:Item), (r:Rule)
                WHERE i.categoryName = "작업 규칙"
                  AND i.content IS NOT NULL
                  AND r.content IS NOT NULL
                  AND (
                    (i.content CONTAINS "답변" AND r.content CONTAINS "답변")
                    OR (i.content CONTAINS "질의" AND r.content CONTAINS "질의")
                    OR (i.content CONTAINS "마크다운" AND r.content CONTAINS "markdown")
                    OR (i.content CONTAINS "목록" AND r.content CONTAINS "목록")
                  )
                MERGE (i)-[rel:RELATED_TO_RULE {matchType: "keyword"}]->(r)
                RETURN count(DISTINCT rel) as created
            """)

            count = result.single()["created"]
            print(f"  ✓ {count}개 Item-Rule 관계 생성됨")

            # 7. QATopic과 Item 간의 주제 연결
            print("\n7️⃣  QATopic ↔ Item 주제별 연결...")
            print("-" * 70)

            result = session.run("""
                MATCH (t:QATopic), (i:Item)
                WHERE t.subcategoryName = i.subcategoryName
                  AND (
                    (t.name CONTAINS "질의" AND i.name CONTAINS "질의")
                    OR (t.name CONTAINS "답변" AND i.name CONTAINS "답변")
                  )
                MERGE (t)-[rel:RELATED_TO_GUIDE]->(i)
                RETURN count(DISTINCT rel) as created
            """)

            count = result.single()["created"]
            print(f"  ✓ {count}개 QATopic-Item 관계 생성됨")

            # 8. 결과 요약
            print("\n" + "=" * 70)
            print("매핑 결과 요약")
            print("=" * 70)

            # 새로 생성된 관계 타입 확인
            result = session.run("""
                MATCH ()-[r]->()
                WHERE type(r) IN ['DESCRIBES_QUERY_TYPE', 'RELATED_TO_RULE', 'RELATED_TO_GUIDE']
                RETURN type(r) as RelationType, count(r) as Count
                ORDER BY Count DESC
            """)

            print("\n새로 생성된 관계:")
            for record in result:
                print(f"  {record['RelationType']:30} : {record['Count']:5} 개")

            # 태그가 추가된 노드 확인
            result = session.run("""
                MATCH (n)
                WHERE n:GuideRule OR n:ContainsExample OR n:ConstraintRelated OR n:BestPracticeRelated
                UNWIND labels(n) as label
                WITH label, count(DISTINCT n) as cnt
                WHERE label IN ['GuideRule', 'ContainsExample', 'ConstraintRelated', 'BestPracticeRelated']
                RETURN label, cnt
                ORDER BY cnt DESC
            """)

            print("\n추가된 태그:")
            for record in result:
                print(f"  {record['label']:30} : {record['cnt']:5} 개")

    def verify_mappings(self):
        """매핑 결과 검증"""
        print("\n" + "=" * 70)
        print("매핑 검증")
        print("=" * 70)

        with self.driver.session() as session:
            # QueryType 연결 확인
            print("\n1. Item → QueryType 연결 확인:")
            result = session.run("""
                MATCH (i:Item)-[r:DESCRIBES_QUERY_TYPE]->(qt:QueryType)
                RETURN i.name as Item, qt.name as QueryType
                ORDER BY qt.name
            """)

            for record in result:
                print(f"  📄 {record['Item']}")
                print(f"     → {record['QueryType']}")

            # GuideRule 확인
            print("\n2. GuideRule 태그가 있는 Item:")
            result = session.run("""
                MATCH (i:GuideRule)
                RETURN i.subcategoryName as Subcategory, i.name as Item
                ORDER BY i.subcategoryName, i.name
                LIMIT 10
            """)

            for record in result:
                print(f"  📋 {record['Subcategory']} > {record['Item']}")

            # 관계 통계
            print("\n3. 전체 관계 통계:")
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as RelationType, count(r) as Count
                ORDER BY Count DESC
                LIMIT 15
            """)

            for record in result:
                print(f"  {record['RelationType']:30} : {record['Count']:5} 개")


def main():
    """메인 함수"""
    uri = os.getenv("NEO4J_URI", "neo4j+s://6a85a996.databases.neo4j.io")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv(
        "NEO4J_PASSWORD", "EfPfVox9wOucwb5d7OvOUzckKZbtNvIdSOwR-y9Rsc8"
    )

    mapper = ManualMapper(uri, username, password)

    try:
        # 매핑 실행
        mapper.execute_mapping()

        # 결과 검증
        mapper.verify_mappings()

        print("\n" + "=" * 70)
        print("✅ 수동 매핑 완료!")
        print("=" * 70)

        print("\nNeo4j Browser에서 확인:")
        print("  https://console.neo4j.io")
        print("\n예제 쿼리:")
        print("  // QueryType 매핑 확인")
        print("  MATCH (i:Item)-[:DESCRIBES_QUERY_TYPE]->(qt:QueryType)")
        print("  RETURN i, qt;")

    finally:
        mapper.close()


if __name__ == "__main__":
    main()
