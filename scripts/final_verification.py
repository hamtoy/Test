import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))
session = driver.session()

# Get counts
demonstrates_result = session.run("MATCH ()-[:DEMONSTRATES]->() RETURN count(*) AS cnt")
demonstrates_count = demonstrates_result.single()["cnt"]

violates_result = session.run("MATCH ()-[:VIOLATES]->() RETURN count(*) AS cnt")
violates_count = violates_result.single()["cnt"]

total_result = session.run("MATCH (e:Example)-[rel]->(r:Rule) RETURN count(*) AS cnt")
total_count = total_result.single()["cnt"]

# Save results
results = []
results.append("=" * 60)
results.append("Example-Rule 수동 매핑 최종 확인")
results.append("=" * 60)
results.append(f"\nDEMONSTRATES 관계: {demonstrates_count}개")
results.append(f"VIOLATES 관계: {violates_count}개")
results.append(f"전체 Example-Rule 관계: {total_count}개")

# Get sample relationships
results.append("\n" + "=" * 60)
results.append("DEMONSTRATES 관계 샘플 (최대 10개)")
results.append("=" * 60)

sample_result = session.run("""
    MATCH (e:Example)-[:DEMONSTRATES]->(r:Rule)
    RETURN e.id AS ex_id, e.text AS ex_text, e.type AS ex_type,
           r.id AS rule_id, r.text AS rule_text
    LIMIT 10
""")

for i, rec in enumerate(sample_result, 1):
    results.append(f"\n{i}. Example [{rec['ex_type']}]: {rec['ex_id']}")
    results.append(f"   Text: {rec['ex_text'][:70]}")
    results.append(f"   → Rule: {rec['rule_id']}")
    results.append(f"   Text: {rec['rule_text'][:70]}")

session.close()
driver.close()

# Print and save
output = "\n".join(results)
print(output)

with open("final_mapping_verification.txt", "w", encoding="utf-8") as f:
    f.write(output)

print("\n✅ final_mapping_verification.txt에 저장됨")
print(f"\n📊 요약: DEMONSTRATES {demonstrates_count}개, VIOLATES {violates_count}개")
