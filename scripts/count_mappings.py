from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
pwd = os.getenv("NEO4J_PASSWORD")

if uri is None or user is None or pwd is None:
    raise EnvironmentError("NEO4J env vars missing")

driver = GraphDatabase.driver(uri, auth=(user, pwd))

with driver.session() as session:
    result = session.run("""
        MATCH (e:Example)-[:DEMONSTRATES]->(r:Rule)
        RETURN count(e) AS mapping_count
    """)
    record = result.single()
    if record is None:
        raise RuntimeError("Query returned no results")
    count = record["mapping_count"]
    print(f"✅ 현재 매핑 수: {count}")

driver.close()
