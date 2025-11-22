import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def debug_descendants():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Finding Column List ===")
        query = """
        MATCH (b:Block)
        WHERE b.type = 'column_list'
        RETURN b.id, b.content
        LIMIT 1
        """
        result = session.run(query)
        record = result.single()
        if not record:
            print("No column_list found.")
            return

        bid = record["b.id"]
        print(f"Column List ID: {bid}")

        print("\n=== Checking Descendants ===")
        query_desc = """
        MATCH (b:Block {id: $id})-[:HAS_CHILD*]->(d:Block)
        RETURN d.type, d.content
        LIMIT 10
        """
        result = session.run(query_desc, id=bid)
        found = False
        for record in result:
            found = True
            content = record["d.content"]
            if content:
                content = content[:30]
            print(f"[{record['d.type']}] {content}")

        if not found:
            print("No descendants found via HAS_CHILD*.")

            # Check direct children
            print("\n=== Checking Direct Children ===")
            query_child = """
            MATCH (b:Block {id: $id})-[r]->(d)
            RETURN type(r), labels(d), d.type
            """
            result = session.run(query_child, id=bid)
            for record in result:
                print(
                    f"-[{record['type(r)']}]-> {record['labels(d)']} ({record['d.type']})"
                )

    driver.close()


if __name__ == "__main__":
    debug_descendants()
