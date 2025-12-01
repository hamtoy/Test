from dotenv import load_dotenv
from neo4j import GraphDatabase
import os

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    result = session.run("""
        MATCH (r:Rule), (qt:QueryType)
        WHERE NOT (r)-[:APPLIES_TO]->(qt)
        MERGE (r)-[:APPLIES_TO]->(qt)
        RETURN count(*) AS created
    """)
    print(f"새로 연결: {result.single()['created']}개")

driver.close()
print("완료!")