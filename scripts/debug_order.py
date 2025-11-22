import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def debug_order():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        print("=== Checking Heading Order ===")
        query_heading = """
        MATCH (p:Page)-[:HAS_BLOCK]->(h:Block)
        WHERE h.type = 'heading_1' AND h.content CONTAINS '자주 틀리는'
        RETURN p.id as page_id, h.id as heading_id, h.order as order, h.content as content
        """
        result = session.run(query_heading)
        headings = list(result)

        if not headings:
            print("No 'Common Mistakes' heading found.")
            return

        for h in headings:
            print(
                f"Heading: {h['content']} (Order: {h['order']}, Page: {h['page_id']})"
            )

            if h["order"] is None:
                print("⚠️ Order is None!")
                continue

            print("\n=== Checking Subsequent Blocks ===")
            query_blocks = """
            MATCH (p:Page {id: $page_id})-[:HAS_BLOCK]->(b:Block)
            WHERE b.order > $start_order
            RETURN b.type as type, b.order as order, b.content as content
            ORDER BY b.order ASC
            LIMIT 10
            """
            blocks = session.run(
                query_blocks, page_id=h["page_id"], start_order=h["order"]
            )
            found_blocks = False
            for b in blocks:
                found_blocks = True
                content = b["content"]
                if content:
                    content = content[:30]
                print(f"[{b['type']}] Order: {b['order']} | {content}")

            if not found_blocks:
                print("No subsequent blocks found.")

    driver.close()


if __name__ == "__main__":
    debug_order()
