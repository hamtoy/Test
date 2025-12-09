"""Fix type field for fewshot examples."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

if not uri or not user or not password:
    raise RuntimeError("Missing NEO4J environment variables")

d = GraphDatabase.driver(uri, auth=(user, password))

with d.session() as session:
    result = session.run("""
        MATCH (e:Example) WHERE e.id STARTS WITH "fewshot_" 
        SET e.type = "positive" 
        RETURN count(e) as updated
    """)
    record = result.single()
    if record:
        print("Updated:", record["updated"], "examples to type=positive")
    else:
        print("No records found")

d.close()
