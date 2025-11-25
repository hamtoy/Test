from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

if uri is None or user is None or password is None:
    raise EnvironmentError("Missing NEO4J environment variables")

driver = GraphDatabase.driver(uri, auth=(user, password))

session = driver.session()

# 통계만 간단히
print("\n=== Neo4j Database Statistics ===\n")

# Rules
stats = session.run("""
    MATCH (r:Rule)
    WITH r,
         CASE WHEN r.is_deleted IS NULL THEN false ELSE r.is_deleted END as deleted_status
    RETURN 
        count(r) as total,
        sum(CASE WHEN deleted_status = true THEN 1 ELSE 0 END) as deleted,
        sum(CASE WHEN deleted_status = false THEN 1 ELSE 0 END) as active
""").single()

if stats is None:
    raise RuntimeError("Rules query returned no results")

print("📋 Rules:")
print(f"  Total: {stats['total']}")
print(f"  Active: {stats['active']}")
print(f"  Deleted: {stats['deleted']}")

# Constraints
stats2 = session.run("""
    MATCH (c:Constraint)
    WITH c,
         CASE WHEN c.is_deleted IS NULL THEN false ELSE c.is_deleted END as deleted_status
    RETURN 
        count(c) as total,
        sum(CASE WHEN deleted_status = true THEN 1 ELSE 0 END) as deleted,
        sum(CASE WHEN deleted_status = false THEN 1 ELSE 0 END) as active
""").single()

if stats2 is None:
    raise RuntimeError("Constraints query returned no results")

print("\n⚠️ Constraints:")
print(f"  Total: {stats2['total']}")
print(f"  Active: {stats2['active']}")
print(f"  Deleted: {stats2['deleted']}")

# Active rules sample
print("\n📌 Active Rules (Sample 5):")
active_rules = session.run("""
    MATCH (r:Rule)
    WHERE r.is_deleted IS NULL OR r.is_deleted = false
    RETURN r.id as id, r.title as title, r.category as category
    LIMIT 5
""")

for i, rec in enumerate(active_rules, 1):
    title = rec["title"] or "No Title"
    category = rec["category"] or "No Category"
    print(f"  {i}. [{category}] {title}")

# Deleted rules sample
print("\n🗑️ Deleted Rules (Sample 5):")
deleted_rules = session.run("""
    MATCH (r:Rule)
    WHERE r.is_deleted = true
    RETURN r.id as id, r.title as title, r.category as category
    LIMIT 5
""")

for i, rec in enumerate(deleted_rules, 1):
    title = rec["title"] or "No Title"
    category = rec["category"] or "No Category"
    print(f"  {i}. [{category}] {title}")

session.close()
driver.close()

print("\n✅ Complete!")
