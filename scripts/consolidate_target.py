"""Consolidate target_short and target_long into target."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    print("=== target_short, target_long 삭제 전 확인 ===")

    # 삭제 전 확인
    result = session.run(
        "MATCH (qt:QueryType) WHERE qt.name IN ['target_short', 'target_long'] RETURN qt.name AS name"
    )
    nodes = list(result)
    print(f"삭제 대상: {[r['name'] for r in nodes]}")

    # 연결된 관계 확인
    result = session.run("""
        MATCH (qt:QueryType)-[r]-()
        WHERE qt.name IN ['target_short', 'target_long']
        RETURN qt.name AS qtype, type(r) AS rel_type, count(r) AS cnt
    """)
    rels = list(result)
    if rels:
        print("연결된 관계:")
        for r in rels:
            print(f"  {r['qtype']}: {r['rel_type']} {r['cnt']}개")
    else:
        print("연결된 관계 없음")

    print()
    print("=== 삭제 실행 ===")
    result = session.run("""
        MATCH (qt:QueryType)
        WHERE qt.name IN ['target_short', 'target_long']
        DETACH DELETE qt
        RETURN count(qt) AS deleted
    """)
    deleted = result.single()["deleted"]
    print(f"삭제된 QueryType 노드: {deleted}개")

    print()
    print("=== 삭제 후 QueryType 확인 ===")
    result = session.run("MATCH (qt:QueryType) RETURN qt.name AS name ORDER BY name")
    for r in result:
        print(f"  - {r['name']}")

driver.close()
print()
print("=== 완료 ===")
