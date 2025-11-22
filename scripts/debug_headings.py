import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def debug_headings():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Headings ===")
        result = session.run(
            """
            MATCH (b:Block)
            WHERE b.type IN ['heading_1', 'heading_2', 'heading_3']
            RETURN b.type AS type, b.content AS content
            LIMIT 50
            """
        )
        for record in result:
            print(f"[{record['type']}] {record['content']}")

    driver.close()


if __name__ == "__main__":
    debug_headings()
