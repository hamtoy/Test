import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def verify_counts() -> None:
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if uri is None or user is None or password is None:
        raise RuntimeError(
            "Missing required Neo4j configuration (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)"
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Node Counts ===")
        for label in ["Rule", "Example", "Page", "Block"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
            record = result.single()
            if record is None:
                print(f"{label}: No data")
                continue
            count = record["count"]
            print(f"{label}: {count}")

    driver.close()


if __name__ == "__main__":
    verify_counts()
