"""
Neo4j Aura 수동 매핑 가능 항목 확인
새로 임포트된 CSV 데이터와 기존 데이터 간의 연결 가능성 분석
"""

import os

from neo4j import GraphDatabase


class MappingAnalyzer:
    """매핑 가능성 분석기"""

    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def analyze_keyword_overlap(self):
        """키워드 기반 매핑 가능성 분석"""
        print("\n🔍 키워드 기반 매핑 가능성 분석")
        print("=" * 70)

        with self.driver.session() as session:
            # Guide Item과 Rule 간의 키워드 매칭
            print("\n1. Guide Item ↔ Rule 매핑:")
            print("-" * 70)

            result = session.run("""
                MATCH (i:Item), (r:Rule)
                WHERE i.content IS NOT NULL 
                  AND r.content IS NOT NULL
                  AND (
                    i.content CONTAINS r.name
                    OR r.name CONTAINS i.name
                    OR (i.content CONTAINS "질의" AND r.content CONTAINS "질의")
                    OR (i.content CONTAINS "답변" AND r.content CONTAINS "답변")
                    OR (i.content CONTAINS "설명문" AND r.content CONTAINS "설명문")
                    OR (i.content CONTAINS "요약문" AND r.content CONTAINS "요약문")
                  )
                RETURN i.categoryName + ' > ' + i.subcategoryName + ' > ' + i.name as ItemPath,
                       r.name as RuleName,
                       substring(i.content, 0, 80) as ItemPreview,
                       substring(r.content, 0, 80) as RulePreview
                LIMIT 20
            """)

            matches = list(result)
            if matches:
                for match in matches:
                    print(f"\n  📄 Item: {match['ItemPath']}")
                    print(f"     → {match['ItemPreview']}...")
                    print(f"  📋 Rule: {match['RuleName']}")
                    print(f"     → {match['RulePreview']}...")
            else:
                print("  매칭 항목 없음")

            # QnA Topic과 Example 간의 매칭
            print("\n\n2. QnA Topic ↔ Example 매핑:")
            print("-" * 70)

            result = session.run("""
                MATCH (t:QATopic), (e:Example)
                WHERE t.content IS NOT NULL 
                  AND e.content IS NOT NULL
                  AND (
                    t.name CONTAINS "예시"
                    OR t.content CONTAINS "예시"
                    OR e.content CONTAINS t.name
                  )
                RETURN t.categoryName + ' > ' + t.subcategoryName + ' > ' + t.name as TopicPath,
                       e.name as ExampleName,
                       substring(t.content, 0, 80) as TopicPreview
                LIMIT 15
            """)

            matches = list(result)
            if matches:
                for match in matches:
                    print(f"\n  ❓ Topic: {match['TopicPath']}")
                    print(f"     → {match['TopicPreview']}...")
                    print(f"  📝 Example: {match['ExampleName']}")
            else:
                print("  매칭 항목 없음")

    def analyze_category_mapping(self):
        """카테고리 기반 매핑 가능성"""
        print("\n\n📂 카테고리 기반 매핑 가능성")
        print("=" * 70)

        with self.driver.session() as session:
            # Guide Category와 QueryType 매핑
            print("\n1. Guide Category와 기존 데이터 타입 비교:")
            print("-" * 70)

            # 기존 데이터 타입 확인
            result = session.run("""
                MATCH (n)
                WHERE NOT n:Category 
                  AND NOT n:Subcategory 
                  AND NOT n:Item
                  AND NOT n:QACategory
                  AND NOT n:QASubcategory
                  AND NOT n:QATopic
                RETURN DISTINCT labels(n)[0] as NodeType, count(n) as Count
                ORDER BY Count DESC
            """)

            print("\n  기존 데이터 타입:")
            for record in result:
                print(f"    - {record['NodeType']:20} : {record['Count']:5} 개")

            # QueryType과의 연결 가능성
            print("\n\n2. QueryType과 Guide 항목 매핑 가능성:")
            print("-" * 70)

            result = session.run("""
                MATCH (qt:QueryType)
                RETURN qt.name as QueryType
                ORDER BY qt.name
            """)

            query_types = [record["QueryType"] for record in result]
            print(f"\n  현재 QueryType: {', '.join(query_types)}")

            # Guide 항목 중 query type 관련된 것들
            result = session.run("""
                MATCH (i:Item)
                WHERE i.name CONTAINS "질의" 
                   OR i.content CONTAINS "target_short"
                   OR i.content CONTAINS "target_long"
                   OR i.content CONTAINS "explanation"
                   OR i.content CONTAINS "reasoning"
                RETURN i.categoryName + ' > ' + i.subcategoryName + ' > ' + i.name as ItemPath,
                       substring(i.content, 0, 100) as Preview
                LIMIT 10
            """)

            print("\n  QueryType과 연결 가능한 Guide 항목:")
            for record in result:
                print(f"\n    📄 {record['ItemPath']}")
                print(f"       → {record['Preview']}...")

    def analyze_constraint_mapping(self):
        """제약조건 매핑 가능성"""
        print("\n\n⚖️ 제약조건(Constraint) 매핑 가능성")
        print("=" * 70)

        with self.driver.session() as session:
            # 기존 Constraint 확인
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.name as ConstraintName,
                       substring(c.content, 0, 100) as Preview
                LIMIT 10
            """)

            print("\n  기존 Constraint 예시:")
            for record in result:
                print(f"\n    ⚖️ {record['ConstraintName']}")
                print(f"       → {record['Preview']}...")

            # Guide/QnA 중 제약조건 관련 항목
            print("\n\n  제약조건과 연결 가능한 항목:")
            result = session.run("""
                MATCH (i:Item)
                WHERE i.content CONTAINS "지양"
                   OR i.content CONTAINS "사용하지 않"
                   OR i.content CONTAINS "불가"
                   OR i.content CONTAINS "금지"
                   OR i.content CONTAINS "반드시"
                RETURN i.name as ItemName,
                       i.categoryName + ' > ' + i.subcategoryName as Path,
                       substring(i.content, 0, 80) as Preview
                LIMIT 10
            """)

            for record in result:
                print(f"\n    📄 {record['Path']} > {record['ItemName']}")
                print(f"       → {record['Preview']}...")

    def analyze_best_practice_mapping(self):
        """BestPractice 매핑 가능성"""
        print("\n\n✨ BestPractice 매핑 가능성")
        print("=" * 70)

        with self.driver.session() as session:
            # 기존 BestPractice 확인
            result = session.run("""
                MATCH (bp:BestPractice)
                RETURN bp.name as BestPracticeName,
                       substring(bp.content, 0, 100) as Preview
            """)

            print("\n  기존 BestPractice:")
            for record in result:
                print(f"\n    ✨ {record['BestPracticeName']}")
                print(f"       → {record['Preview']}...")

            # Guide/QnA 중 best practice 관련 항목
            print("\n\n  BestPractice와 연결 가능한 항목:")
            result = session.run("""
                MATCH (i:Item)
                WHERE i.content CONTAINS "지향"
                   OR i.content CONTAINS "원칙"
                   OR i.content CONTAINS "권장"
                   OR i.content CONTAINS "올바른"
                   OR i.name CONTAINS "주의사항"
                RETURN i.name as ItemName,
                       i.categoryName + ' > ' + i.subcategoryName as Path,
                       substring(i.content, 0, 80) as Preview
                LIMIT 10
            """)

            for record in result:
                print(f"\n    📄 {record['Path']} > {record['ItemName']}")
                print(f"       → {record['Preview']}...")

    def suggest_manual_mappings(self):
        """수동 매핑 제안"""
        print("\n\n💡 수동 매핑 제안")
        print("=" * 70)

        suggestions = [
            {
                "매핑": "Item (질의 관련) → QueryType",
                "이유": "Guide의 질의 유형 설명과 QueryType 연결",
                "쿼리": """
MATCH (i:Item)
WHERE i.name CONTAINS "질의"
WITH i
MATCH (qt:QueryType)
WHERE i.content CONTAINS qt.name
MERGE (i)-[:DESCRIBES]->(qt)
RETURN count(*) as CreatedLinks;
                """,
            },
            {
                "매핑": "Item (작업 규칙) → Rule",
                "이유": "작업 규칙과 Rule 노드 연결",
                "쿼리": """
MATCH (i:Item)
WHERE i.categoryName = "작업 규칙"
WITH i
MATCH (r:Rule)
WHERE r.name CONTAINS i.name 
   OR i.content CONTAINS r.name
MERGE (i)-[:DEFINES]->(r)
RETURN count(*) as CreatedLinks;
                """,
            },
            {
                "매핑": "QATopic (예시 포함) → Example",
                "이유": "FAQ 내용과 Example 연결",
                "쿼리": """
MATCH (t:QATopic)
WHERE t.content CONTAINS "예시"
WITH t
MATCH (e:Example)
WHERE e.content CONTAINS t.name
   OR t.content CONTAINS e.name
MERGE (t)-[:REFERENCES]->(e)
RETURN count(*) as CreatedLinks;
                """,
            },
            {
                "매핑": "Item → Constraint",
                "이유": "제약조건 관련 가이드와 Constraint 연결",
                "쿼리": """
MATCH (i:Item)
WHERE i.content CONTAINS "불가" 
   OR i.content CONTAINS "금지"
   OR i.content CONTAINS "반드시"
WITH i
MATCH (c:Constraint)
WHERE c.content CONTAINS i.name
MERGE (i)-[:ENFORCES_RULE]->(c)
RETURN count(*) as CreatedLinks;
                """,
            },
            {
                "매핑": "Item → BestPractice",
                "이유": "좋은 예시와 BestPractice 연결",
                "쿼리": """
MATCH (i:Item)
WHERE i.content CONTAINS "지향"
   OR i.content CONTAINS "권장"
   OR i.name CONTAINS "주의사항"
WITH i
MATCH (bp:BestPractice)
MERGE (i)-[:RECOMMENDS]->(bp)
RETURN count(*) as CreatedLinks;
                """,
            },
        ]

        for idx, suggestion in enumerate(suggestions, 1):
            print(f"\n{idx}. {suggestion['매핑']}")
            print(f"   이유: {suggestion['이유']}")
            print(f"   쿼리:\n```cypher\n{suggestion['쿼리'].strip()}\n```")

    def generate_mapping_script(self):
        """자동 매핑 스크립트 생성"""
        print("\n\n🤖 자동 매핑 실행 스크립트")
        print("=" * 70)

        with self.driver.session() as session:
            print("\n매핑 실행 중...")

            # 1. Item과 QueryType 연결 (내용 기반)
            result = session.run("""
                MATCH (i:Item), (qt:QueryType)
                WHERE i.content IS NOT NULL
                  AND qt.name IS NOT NULL
                  AND (
                    toLower(i.content) CONTAINS toLower(qt.name)
                    OR toLower(i.name) CONTAINS toLower(qt.name)
                  )
                MERGE (i)-[:RELATED_TO_QUERY_TYPE]->(qt)
                RETURN count(*) as LinksCreated
            """)
            count1 = result.single()["LinksCreated"]
            print(f"  ✓ Item → QueryType: {count1} 개 연결")

            # 2. QATopic과 Example 연결
            result = session.run("""
                MATCH (t:QATopic), (e:Example)
                WHERE t.content IS NOT NULL
                  AND e.content IS NOT NULL
                  AND t.content CONTAINS "예시"
                MERGE (t)-[:REFERENCES_EXAMPLE]->(e)
                RETURN count(*) as LinksCreated
            """)
            count2 = result.single()["LinksCreated"]
            print(f"  ✓ QATopic → Example: {count2} 개 연결")

            # 3. Item과 Rule 연결 (작업 규칙)
            result = session.run("""
                MATCH (i:Item), (r:Rule)
                WHERE i.categoryName = "작업 규칙"
                  AND i.content IS NOT NULL
                  AND r.content IS NOT NULL
                MERGE (i)-[:DEFINES_RULE]->(r)
                RETURN count(*) as LinksCreated
            """)
            count3 = result.single()["LinksCreated"]
            print(f"  ✓ Item → Rule: {count3} 개 연결")

            print(f"\n  총 {count1 + count2 + count3} 개의 관계 생성됨!")


def main():
    """메인 함수"""
    uri = os.getenv("NEO4J_URI", "neo4j+s://6a85a996.databases.neo4j.io")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv(
        "NEO4J_PASSWORD", "EfPfVox9wOucwb5d7OvOUzckKZbtNvIdSOwR-y9Rsc8"
    )

    analyzer = MappingAnalyzer(uri, username, password)

    try:
        print("=" * 70)
        print("Neo4j Aura 수동 매핑 가능 항목 분석")
        print("=" * 70)

        # 분석 실행
        analyzer.analyze_keyword_overlap()
        analyzer.analyze_category_mapping()
        analyzer.analyze_constraint_mapping()
        analyzer.analyze_best_practice_mapping()
        analyzer.suggest_manual_mappings()

        # 자동 매핑 실행 여부 확인
        print("\n\n" + "=" * 70)
        response = input("자동 매핑을 실행하시겠습니까? (y/n): ")

        if response.lower() == "y":
            analyzer.generate_mapping_script()
            print("\n✅ 자동 매핑 완료!")
        else:
            print("\n⏸️  자동 매핑을 건너뜁니다.")

    finally:
        analyzer.close()

    print("\n" + "=" * 70)
    print("✅ 분석 완료!")
    print("=" * 70)


if __name__ == "__main__":
    main()
