"""Check Neo4j constraints and rules status."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    print("=== 1. QueryType 노드 확인 ===")
    result = session.run("MATCH (qt:QueryType) RETURN qt.name AS name LIMIT 10")
    records = list(result)
    if records:
        for r in records:
            print(f"  - {r['name']}")
    else:
        print("  QueryType 노드 없음!")

    print()
    print("=== 2. Constraint 노드 확인 ===")
    result = session.run(
        "MATCH (c:Constraint) RETURN c.id AS id, c.category AS category, c.description AS desc LIMIT 10"
    )
    records = list(result)
    if records:
        for r in records:
            desc_str = str(r["desc"])[:50] if r["desc"] else "N/A"
            print(f"  ID: {r['id']}, Category: {r['category']}, Desc: {desc_str}...")
    else:
        print("  Constraint 노드 없음!")

    print()
    print("=== 3. QueryType-HAS_CONSTRAINT 관계 확인 ===")
    result = session.run(
        "MATCH (qt:QueryType)-[:HAS_CONSTRAINT]->(c:Constraint) RETURN qt.name AS qt, c.id AS cid, c.category AS cat LIMIT 10"
    )
    records = list(result)
    if records:
        for r in records:
            print(f"  {r['qt']} -> {r['cid']} (category: {r['cat']})")
    else:
        print("  HAS_CONSTRAINT 관계 없음!")

    print()
    print("=== 4. FormattingRule 노드 확인 ===")
    result = session.run(
        "MATCH (fr:FormattingRule) RETURN fr.name AS name, fr.description AS desc, fr.applies_to AS applies_to LIMIT 10"
    )
    records = list(result)
    if records:
        for r in records:
            desc_str = str(r["desc"])[:40] if r["desc"] else "N/A"
            print(
                f"  Name: {r['name']}, AppliesTo: {r['applies_to']}, Desc: {desc_str}..."
            )
    else:
        print("  FormattingRule 노드 없음!")

    print()
    print("=== 5. Rule 노드 확인 ===")
    result = session.run(
        "MATCH (r:Rule) RETURN r.id AS id, r.category AS category, r.applies_to AS applies_to LIMIT 10"
    )
    records = list(result)
    if records:
        for r in records:
            print(
                f"  ID: {r['id']}, Category: {r['category']}, AppliesTo: {r['applies_to']}"
            )
    else:
        print("  Rule 노드 없음!")

    print()
    print("=== 6. summary QueryType 연결 확인 ===")
    result = session.run("""
        MATCH (qt:QueryType {name: 'summary'})-[r]-(n)
        RETURN type(r) AS rel_type, labels(n) AS node_labels, n.id AS node_id, n.name AS node_name
        LIMIT 20
    """)
    records = list(result)
    if records:
        for r in records:
            print(
                f"  {r['rel_type']} -> {r['node_labels']}: {r['node_id'] or r['node_name']}"
            )
    else:
        print("  연결된 노드 없음!")

    print()
    print("=== 7. 전체 노드 통계 ===")
    result = session.run("""
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS cnt
        ORDER BY cnt DESC
    """)
    for r in result:
        print(f"  {r['label']}: {r['cnt']}개")

driver.close()
print()
print("=== 완료 ===")
