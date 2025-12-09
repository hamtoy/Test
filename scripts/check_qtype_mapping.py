"""Check QTYPE_MAP vs Neo4j QueryType mapping."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Get environment variables with defaults
neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USER")
neo4j_password = os.getenv("NEO4J_PASSWORD")

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError("NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set")

driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

# 코드에서 사용하는 QTYPE_MAP
QTYPE_MAP = {
    "global_explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target",
}

print("=== QTYPE_MAP vs Neo4j QueryType 매핑 확인 ===")
print()

with driver.session() as session:
    for api_type, normalized in QTYPE_MAP.items():
        print(f"API: {api_type} -> Neo4j: {normalized}")

        # Rule 연결 확인 (APPLIES_TO 관계)
        result = session.run(
            "MATCH (qt:QueryType {name: $qtype})<-[:APPLIES_TO]-(r:Rule) RETURN count(r) AS rule_count",
            qtype=normalized,
        )
        record = result.single()
        rule_count = record["rule_count"] if record else 0

        # Constraint 연결 확인 (HAS_CONSTRAINT 관계)
        result = session.run(
            "MATCH (qt:QueryType {name: $qtype})-[:HAS_CONSTRAINT]->(c:Constraint) RETURN count(c) AS constraint_count",
            qtype=normalized,
        )
        record = result.single()
        constraint_count = record["constraint_count"] if record else 0

        print(f"  -> Rule: {rule_count}개, Constraint: {constraint_count}개")
        print()

    # 모든 QueryType별 Rule/Constraint 연결 통계
    print("=== 전체 QueryType별 Rule 연결 통계 ===")
    result = session.run("""
        MATCH (qt:QueryType)
        OPTIONAL MATCH (qt)<-[:APPLIES_TO]-(r:Rule)
        OPTIONAL MATCH (qt)-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN qt.name AS qtype, count(DISTINCT r) AS rules, count(DISTINCT c) AS constraints
        ORDER BY qt.name
    """)
    for r in result:
        print(f"  {r['qtype']}: Rule {r['rules']}개, Constraint {r['constraints']}개")

driver.close()
print()
print("=== 완료 ===")
