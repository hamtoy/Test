import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

neo4j_uri = os.getenv("NEO4J_URI")
neo4j_user = os.getenv("NEO4J_USER")
neo4j_password = os.getenv("NEO4J_PASSWORD")

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError("Missing Neo4j credentials in environment variables")

driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

with driver.session() as session:
    # Count relationships
    dem_result = session.run(
        "MATCH ()-[:DEMONSTRATES]->() RETURN count(*) AS c"
    ).single()
    vio_result = session.run("MATCH ()-[:VIOLATES]->() RETURN count(*) AS c").single()
    total_result = session.run(
        "MATCH (e:Example)-[]->(r:Rule) RETURN count(*) AS c"
    ).single()

    if dem_result and vio_result and total_result:
        dem = dem_result["c"]
        vio = vio_result["c"]
        total = total_result["c"]

        print(f"DEMONSTRATES: {dem}")
        print(f"VIOLATES: {vio}")
        print(f"Total Example-Rule: {total}")

driver.close()
