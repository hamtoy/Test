import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def dump_block():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Dumping Block Relationships ===")
        # Find a block with some content
        query = """
        MATCH (b:Block)
        WHERE size(b.content) > 10
        RETURN b.id, b.content
        LIMIT 1
        """
        result = session.run(query)
        record = result.single()
        if not record:
            print("No blocks found.")
            return

        bid = record["b.id"]
        print(f"Block ID: {bid}")
        print(f"Content: {record['b.content'][:50]}...")

        # Get all relationships
        query_rel = """
        MATCH (b:Block {id: $id})-[r]-(n)
        RETURN type(r) AS rel_type, startNode(r).id AS start_id, endNode(r).id AS end_id, labels(n) AS target_labels
        """
        result = session.run(query_rel, id=bid)
        for record in result:
            direction = "->" if record["start_id"] == bid else "<-"
            print(f"{direction} [{record['rel_type']}] {record['target_labels']}")

    driver.close()


if __name__ == "__main__":
    dump_block()
