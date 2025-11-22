import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def fetch_ids():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Rules ===")
        result = session.run(
            "MATCH (r:Rule) RETURN r.id AS id, left(r.text, 80) AS text"
        )
        for record in result:
            print(f"ID: {record['id']} | Text: {record['text']}...")

        print("\n=== Examples ===")
        result = session.run(
            "MATCH (e:Example) RETURN e.id AS id, left(e.text, 80) AS text, e.type AS type"
        )
        for record in result:
            print(
                f"ID: {record['id']} | Type: {record['type']} | Text: {record['text']}..."
            )

    driver.close()


if __name__ == "__main__":
    fetch_ids()
