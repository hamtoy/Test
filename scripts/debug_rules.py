import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def debug_rules() -> None:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if uri is None or user is None or password is None:
        raise RuntimeError(
            "Missing required Neo4j configuration (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)"
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Checking NEXT relationships ===")
        result = session.run("MATCH ()-[r:NEXT]->() RETURN count(r) AS count")
        record = result.single()
        if record is None:
            print("Total NEXT relationships: No data")
        else:
            print(f"Total NEXT relationships: {record['count']}")

        print("\n=== Checking Heading Siblings ===")
        query_siblings = """
        MATCH (h:Block)
        WHERE h.type = 'heading_1' AND h.content CONTAINS '자주 틀리는'
        MATCH (parent)-[:CONTAINS]->(h)
        MATCH (parent)-[:CONTAINS]->(sibling:Block)
        RETURN sibling.type AS type, sibling.content AS content
        LIMIT 20
        """
        result = session.run(query_siblings)
        for record in result:
            content = record["content"]
            content = content[:50] if content else "N/A"
            print(f"[{record['type']}] {content}")

    driver.close()


if __name__ == "__main__":
    debug_rules()
