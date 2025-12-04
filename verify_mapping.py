import os

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver, Record

load_dotenv()


def require_env(key: str) -> str:
    """Fetch required env var or raise."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing environment variable: {key}")
    return value


driver: Driver = GraphDatabase.driver(
    require_env("NEO4J_URI"),
    auth=(require_env("NEO4J_USER"), require_env("NEO4J_PASSWORD")),
)

with driver.session() as session:
    print("=== 생성된 Rule 확인 ===")
    result = session.run("""
        MATCH (fc:FeedbackCategory)-[:GENERATED_RULE]->(r:Rule)
        RETURN fc.name AS category,
               r.id AS rule_id,
               r.priority AS priority,
               r.text AS text
        ORDER BY priority DESC, category
    """)
    for record in result:
        priority = record["priority"].upper()
        category = record["category"]
        rule_id = record["rule_id"]
        text = record["text"]
        print(f"\n[{priority}] {category}")
        print(f"  ID: {rule_id}")
        print(f"  내용: {text}")

    print("\n\n=== 생성된 Constraint 확인 ===")
    result = session.run("""
        MATCH (fc:FeedbackCategory)-[:SUGGESTS_CONSTRAINT]->(c:Constraint)
        RETURN fc.name AS category,
               c.id AS constraint_id,
               c.type AS type,
               c.description AS description,
               c.severity AS severity
        ORDER BY c.severity DESC
    """)
    for record in result:
        severity = record["severity"].upper()
        category = record["category"]
        constraint_id = record["constraint_id"]
        ctype = record["type"]
        description = record["description"]
        print(f"\n[{severity}] {category}")
        print(f"  ID: {constraint_id}")
        print(f"  Type: {ctype}")
        print(f"  설명: {description}")

    print("\n\n=== 통계 요약 ===")
    result = session.run("""
        MATCH (fc:FeedbackCategory)
        OPTIONAL MATCH (fc)-[:GENERATED_RULE]->(r)
        OPTIONAL MATCH (fc)-[:SUGGESTS_CONSTRAINT]->(c)
        OPTIONAL MATCH (f)-[:CATEGORIZED_AS]->(fc)
        RETURN count(DISTINCT fc) AS categories,
               count(DISTINCT r) AS rules,
               count(DISTINCT c) AS constraints,
               count(DISTINCT f) AS feedbacks
    """)
    stats: Record | None = result.single()
    if stats:
        print(f"  카테고리: {stats['categories']}개")
        print(f"  생성된 Rule: {stats['rules']}개")
        print(f"  생성된 Constraint: {stats['constraints']}개")
        print(f"  전체 피드백: {stats['feedbacks']}개")
    else:
        print("  통계 결과를 조회하지 못했습니다.")

driver.close()
print("\n✅ 검증 완료!")
