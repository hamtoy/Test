"""Add dedicated no-prose-bold constraint to Neo4j."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    print("=== 볼드체 금지 전용 Constraint 추가 ===")
    print()

    # 1. 볼드체 금지 Constraint 생성
    result = session.run("""
        MERGE (c:Constraint {id: 'no_prose_bold'})
        SET c.type = 'formatting',
            c.description = '본문 문장 내 숫자/단어에 볼드체(**) 사용 절대 금지. 예: **1.34**, **상승**, **100달러** 등 금지.',
            c.severity = 'error',
            c.priority = 95,
            c.category = 'answer',
            c.pattern = '(?<!^)(?<!- )(?<!\\d\\. )\\*\\*[^*]+\\*\\*',
            c.example_bad = '구인배율은 **1.34**를 기록했습니다.',
            c.example_good = '구인배율은 1.34를 기록했습니다.'
        RETURN c.id AS id
    """)
    constraint_id = result.single()["id"]
    print(f"생성된 Constraint: {constraint_id}")

    # 2. 모든 QueryType에 연결
    result = session.run("""
        MATCH (qt:QueryType), (c:Constraint {id: 'no_prose_bold'})
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        RETURN count(*) AS created
    """)
    created = result.single()["created"]
    print(f"HAS_CONSTRAINT 관계 생성: {created}개")

    print()
    print("=== 검증: Constraint 목록 ===")
    result = session.run("""
        MATCH (c:Constraint)
        RETURN c.id AS id, c.priority AS priority, c.severity AS severity
        ORDER BY c.priority DESC
        LIMIT 10
    """)
    for r in result:
        print(f"  {r['id']}: priority={r['priority']}, severity={r['severity']}")

    print()
    print("=== 검증: QueryType별 Constraint 개수 ===")
    result = session.run("""
        MATCH (qt:QueryType)-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN qt.name AS qtype, count(c) AS cnt
        ORDER BY qt.name
    """)
    for r in result:
        print(f"  {r['qtype']}: {r['cnt']}개")

driver.close()
print()
print("=== 완료 ===")
