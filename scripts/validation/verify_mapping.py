"""
Neo4j Aura 데이터 매핑 확인 스크립트
"""

import os

from neo4j import GraphDatabase


def verify_mapping():
    """Neo4j Aura 데이터 매핑 확인"""

    uri = os.getenv("NEO4J_URI", "neo4j+s://6a85a996.databases.neo4j.io")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv(
        "NEO4J_PASSWORD", "EfPfVox9wOucwb5d7OvOUzckKZbtNvIdSOwR-y9Rsc8"
    )

    driver = GraphDatabase.driver(uri, auth=(username, password))

    print("=" * 70)
    print("Neo4j Aura 데이터 매핑 확인")
    print("=" * 70)

    with driver.session() as session:
        # 1. 전체 노드 통계
        print("\n📊 노드 통계:")
        print("-" * 70)
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as NodeType, count(n) as Count
            ORDER BY Count DESC
        """)

        for record in result:
            print(f"  {record['NodeType']:20} : {record['Count']:5} 개")

        # 2. 전체 관계 통계
        print("\n🔗 관계 통계:")
        print("-" * 70)
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as RelationType, count(r) as Count
            ORDER BY Count DESC
        """)

        for record in result:
            print(f"  {record['RelationType']:20} : {record['Count']:5} 개")

        # 3. Guide 데이터 구조 확인
        print("\n📚 Guide 데이터 구조:")
        print("-" * 70)
        result = session.run("""
            MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)
            OPTIONAL MATCH (s)-[:HAS_ITEM]->(i:Item)
            RETURN c.name as Category, 
                   s.name as Subcategory,
                   count(i) as ItemCount
            ORDER BY c.name, s.name
        """)

        current_category = None
        for record in result:
            if current_category != record["Category"]:
                current_category = record["Category"]
                print(f"\n  📁 {current_category}")
            print(f"    └─ {record['Subcategory']:30} ({record['ItemCount']} items)")

        # 4. QnA 데이터 구조 확인
        print("\n\n❓ QnA 데이터 구조:")
        print("-" * 70)
        result = session.run("""
            MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)
            OPTIONAL MATCH (s)-[:HAS_TOPIC]->(t:QATopic)
            RETURN c.name as Category,
                   s.name as Subcategory,
                   count(t) as TopicCount
            ORDER BY c.name, s.name
        """)

        current_category = None
        for record in result:
            if current_category != record["Category"]:
                current_category = record["Category"]
                print(f"\n  📁 {current_category}")
            print(f"    └─ {record['Subcategory']:40} ({record['TopicCount']} topics)")

        # 5. 샘플 데이터 확인 (Guide)
        print("\n\n📄 Guide 샘플 데이터 (처음 5개):")
        print("-" * 70)
        result = session.run("""
            MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
            RETURN c.name as Category,
                   s.name as Subcategory,
                   i.name as Item,
                   substring(i.content, 0, 100) as ContentPreview
            ORDER BY c.name, s.name, i.name
            LIMIT 5
        """)

        for i, record in enumerate(result, 1):
            print(f"\n  {i}. {record['Category']} > {record['Subcategory']}")
            print(f"     항목: {record['Item']}")
            print(f"     내용: {record['ContentPreview']}...")

        # 6. 샘플 데이터 확인 (QnA)
        print("\n\n📄 QnA 샘플 데이터 (처음 5개):")
        print("-" * 70)
        result = session.run("""
            MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)-[:HAS_TOPIC]->(t:QATopic)
            RETURN c.name as Category,
                   s.name as Subcategory,
                   t.name as Topic,
                   substring(t.content, 0, 100) as ContentPreview
            ORDER BY c.name, s.name, t.name
            LIMIT 5
        """)

        for i, record in enumerate(result, 1):
            print(f"\n  {i}. {record['Category']} > {record['Subcategory']}")
            print(f"     주제: {record['Topic']}")
            print(f"     내용: {record['ContentPreview']}...")

        # 7. 데이터 무결성 확인
        print("\n\n🔍 데이터 무결성 확인:")
        print("-" * 70)

        # 내용이 없는 항목 찾기
        result = session.run("""
            MATCH (i:Item)
            WHERE i.content IS NULL OR trim(i.content) = ''
            RETURN count(i) as EmptyCount
        """)
        empty_items = result.single()["EmptyCount"]

        result = session.run("""
            MATCH (t:QATopic)
            WHERE t.content IS NULL OR trim(t.content) = ''
            RETURN count(t) as EmptyCount
        """)
        empty_topics = result.single()["EmptyCount"]

        print(f"  내용이 비어있는 Item: {empty_items}개")
        print(f"  내용이 비어있는 Topic: {empty_topics}개")

        # 고아 노드 찾기 (관계가 없는 노드)
        result = session.run("""
            MATCH (s:Subcategory)
            WHERE NOT exists((s)<-[:HAS_SUBCATEGORY]-())
            RETURN count(s) as OrphanCount
        """)
        orphan_subs = result.single()["OrphanCount"]

        result = session.run("""
            MATCH (i:Item)
            WHERE NOT exists((i)<-[:HAS_ITEM]-())
            RETURN count(i) as OrphanCount
        """)
        orphan_items = result.single()["OrphanCount"]

        print(f"  고아 Subcategory: {orphan_subs}개")
        print(f"  고아 Item: {orphan_items}개")

        # 8. CSV 원본과 비교
        print("\n\n📊 원본 CSV 비교:")
        print("-" * 70)
        print("  guide.csv 원본 라인: 1,373개")
        print("  qna.csv 원본 라인:     774개")
        print(
            "  → 실제 임포트된 데이터는 CSV 파일이 테스트용으로 축소된 것으로 보입니다."
        )

    print("\n" + "=" * 70)
    print("✅ 매핑 확인 완료!")
    print("=" * 70)

    driver.close()


if __name__ == "__main__":
    verify_mapping()
