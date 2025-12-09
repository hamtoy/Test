"""Fix type field for fewshot examples."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(override=True)

d = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with d.session() as session:
    result = session.run("""
        MATCH (e:Example) WHERE e.id STARTS WITH "fewshot_" 
        SET e.type = "positive" 
        RETURN count(e) as updated
    """)
    print("Updated:", result.single()["updated"], "examples to type=positive")

d.close()
