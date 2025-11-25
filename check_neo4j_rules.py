from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

session = driver.session()

# Rule 노드 조회
print("\n=== Neo4j Rules (Sample) ===")
result = session.run("""
    MATCH (r:Rule) 
    RETURN r.id as id, r.title as title, r.category as category, 
           r.content as content, r.is_deleted as is_deleted
    LIMIT 20
""")

for rec in result:
    print(f"ID: {rec['id']}")
    print(f"Title: {rec['title']}")
    print(f"Category: {rec['category']}")
    print(f"Deleted: {rec.get('is_deleted', False)}")
    content = rec["content"][:150] if rec["content"] else "None"
    print(f"Content: {content}...")
    print("---\n")

# 통계
print("\n=== Statistics ===")
stats = session.run("""
    MATCH (r:Rule)
    RETURN 
        count(r) as total_rules,
        sum(CASE WHEN r.is_deleted = true THEN 1 ELSE 0 END) as deleted_rules,
        sum(CASE WHEN r.is_deleted = false OR r.is_deleted IS NULL THEN 1 ELSE 0 END) as active_rules
""").single()

print(f"Total Rules: {stats['total_rules']}")
print(f"Deleted Rules: {stats['deleted_rules']}")
print(f"Active Rules: {stats['active_rules']}")

# Constraint 조회
print("\n=== Neo4j Constraints (Sample) ===")
result2 = session.run("""
    MATCH (c:Constraint)
    RETURN c.id as id, c.title as title, c.type as type,
           c.is_deleted as is_deleted
    LIMIT 10
""")

for rec in result2:
    print(f"ID: {rec['id']}")
    print(f"Title: {rec['title']}")
    print(f"Type: {rec['type']}")
    print(f"Deleted: {rec.get('is_deleted', False)}")
    print("---\n")

session.close()
driver.close()
