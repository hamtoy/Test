import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as session:
    # Count relationships
    dem = session.run("MATCH ()-[:DEMONSTRATES]->() RETURN count(*) AS c").single()["c"]
    vio = session.run("MATCH ()-[:VIOLATES]->() RETURN count(*) AS c").single()["c"]
    total = session.run("MATCH (e:Example)-[]->(r:Rule) RETURN count(*) AS c").single()[
        "c"
    ]

    print(f"DEMONSTRATES: {dem}")
    print(f"VIOLATES: {vio}")
    print(f"Total Example-Rule: {total}")

driver.close()
