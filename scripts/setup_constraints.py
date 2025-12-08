"""Create HAS_CONSTRAINT relationships and set category on Constraint nodes."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    print("=== 1. 현재 Constraint 노드 확인 ===")
    result = session.run(
        "MATCH (c:Constraint) RETURN c.id AS id, c.description AS desc, c.category AS cat"
    )
    constraints = list(result)
    for c in constraints:
        desc = str(c["desc"])[:50] if c["desc"] else "N/A"
        print(f"  {c['id']}: category={c['cat']}, desc={desc}...")

    print()
    print("=== 2. Constraint에 category='answer' 설정 ===")
    result = session.run("""
        MATCH (c:Constraint)
        WHERE c.category IS NULL
        SET c.category = 'answer'
        RETURN count(c) AS updated
    """)
    updated = result.single()["updated"]
    print(f"  업데이트된 Constraint: {updated}개")

    print()
    print("=== 3. HAS_CONSTRAINT 관계 생성 ===")
    result = session.run("""
        MATCH (qt:QueryType), (c:Constraint)
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        RETURN count(*) AS created
    """)
    created = result.single()["created"]
    print(f"  생성된 HAS_CONSTRAINT 관계: {created}개")

    print()
    print("=== 4. 검증: QueryType별 Constraint 연결 확인 ===")
    result = session.run("""
        MATCH (qt:QueryType)-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN qt.name AS qtype, count(c) AS cnt, collect(c.category)[0] AS cat
        ORDER BY qt.name
    """)
    for r in result:
        print(f"  {r['qtype']}: {r['cnt']}개 Constraint (category: {r['cat']})")

driver.close()
print()
print("=== 완료 ===")
